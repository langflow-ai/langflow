//! Dense copy-on-write rows for committed snapshots.
//!
//! A clone shares the root. A write copies only its search path and at most
//! one small leaf while an earlier snapshot is alive. Empty leaves and
//! branches disappear on removal; metadata never refers to old revisions.

use std::ops::Index;
use std::sync::Arc;

const LEAF_CAPACITY: usize = 32;

#[derive(Debug)]
enum Node<T> {
    Leaf(Vec<T>),
    Branch {
        left: Arc<Self>,
        right: Arc<Self>,
        len: usize,
        height: u8,
    },
}

impl<T: Clone> Clone for Node<T> {
    fn clone(&self) -> Self {
        match self {
            Self::Leaf(rows) => {
                let mut copy = Vec::with_capacity(LEAF_CAPACITY);
                copy.extend(rows.iter().cloned());
                Self::Leaf(copy)
            }
            Self::Branch {
                left,
                right,
                len,
                height,
            } => Self::Branch {
                left: Arc::clone(left),
                right: Arc::clone(right),
                len: *len,
                height: *height,
            },
        }
    }
}

impl<T> Node<T> {
    fn len(&self) -> usize {
        match self {
            Self::Leaf(rows) => rows.len(),
            Self::Branch { len, .. } => *len,
        }
    }

    fn height(&self) -> u8 {
        match self {
            Self::Leaf(rows) => u8::from(!rows.is_empty()),
            Self::Branch { height, .. } => *height,
        }
    }

    fn branch(left: Arc<Self>, right: Arc<Self>) -> Self {
        Self::Branch {
            len: left.len() + right.len(),
            height: 1 + left.height().max(right.height()),
            left,
            right,
        }
    }

    fn get(&self, index: usize) -> Option<&T> {
        match self {
            Self::Leaf(rows) => rows.get(index),
            Self::Branch { left, right, .. } => {
                if index < left.len() {
                    left.get(index)
                } else {
                    right.get(index - left.len())
                }
            }
        }
    }
}

/// An ordered sequence with constant-time snapshot clones.
#[derive(Debug, Clone)]
pub(super) struct Rows<T> {
    root: Option<Arc<Node<T>>>,
}

impl<T> Default for Rows<T> {
    fn default() -> Self {
        Self { root: None }
    }
}

impl<T: Clone> Rows<T> {
    pub(super) fn len(&self) -> usize {
        self.root.as_ref().map_or(0, |root| root.len())
    }

    pub(super) fn get_mut(&mut self, index: usize) -> Option<&mut T> {
        fn get<T: Clone>(node: &mut Arc<Node<T>>, index: usize) -> Option<&mut T> {
            match Arc::make_mut(node) {
                Node::Leaf(rows) => rows.get_mut(index),
                Node::Branch { left, right, .. } => {
                    if index < left.len() {
                        get(left, index)
                    } else {
                        get(right, index - left.len())
                    }
                }
            }
        }
        if index >= self.len() {
            return None;
        }
        get(self.root.as_mut()?, index)
    }

    pub(super) fn set(&mut self, index: usize, value: T) {
        *self.get_mut(index).expect("the snapshot row exists") = value;
    }

    pub(super) fn push_back(&mut self, value: T) {
        fn push<T: Clone>(node: &mut Arc<Node<T>>, value: T) {
            match Arc::make_mut(node) {
                Node::Leaf(rows) if rows.len() < LEAF_CAPACITY => rows.push(value),
                Node::Leaf(rows) => {
                    let old = std::mem::take(rows);
                    let mut new = Vec::with_capacity(LEAF_CAPACITY);
                    new.push(value);
                    *Arc::make_mut(node) =
                        Node::branch(Arc::new(Node::Leaf(old)), Arc::new(Node::Leaf(new)));
                }
                Node::Branch { right, .. } => {
                    push(right, value);
                    balance(node);
                }
            }
        }
        if let Some(root) = &mut self.root {
            push(root, value);
        } else {
            let mut rows = Vec::with_capacity(LEAF_CAPACITY);
            rows.push(value);
            self.root = Some(Arc::new(Node::Leaf(rows)));
        }
    }

    #[cfg(test)]
    pub(super) fn remove(&mut self, index: usize) -> T {
        fn remove<T: Clone>(node: &mut Arc<Node<T>>, index: usize) -> T {
            let value = match Arc::make_mut(node) {
                Node::Leaf(rows) => rows.remove(index),
                Node::Branch { left, right, .. } => {
                    if index < left.len() {
                        remove(left, index)
                    } else {
                        remove(right, index - left.len())
                    }
                }
            };
            balance(node);
            value
        }
        assert!(index < self.len(), "the snapshot row exists");
        let value = remove(self.root.as_mut().expect("rows exist"), index);
        if self.len() == 0 {
            self.root = None;
        }
        value
    }

    pub(super) fn iter(&self) -> Iter<'_, T> {
        let mut iter = Iter {
            branches: Vec::new(),
            leaf: [].iter(),
            remaining: self.len(),
        };
        if let Some(root) = &self.root {
            iter.descend(root);
        }
        iter
    }
}

fn balance<T: Clone>(root: &mut Arc<Node<T>>) {
    let Node::Branch {
        left,
        right,
        len,
        height,
    } = Arc::make_mut(root)
    else {
        return;
    };
    *len = left.len() + right.len();
    *height = 1 + left.height().max(right.height());
    if left.len() == 0 {
        *root = Arc::clone(right);
        return;
    }
    if right.len() == 0 {
        *root = Arc::clone(left);
        return;
    }
    let delta = i16::from(left.height()) - i16::from(right.height());
    if delta > 1 {
        if let Node::Branch {
            left: a, right: b, ..
        } = left.as_ref()
            && a.height() < b.height()
        {
            rotate_left(left);
        }
        rotate_right(root);
    } else if delta < -1 {
        if let Node::Branch {
            left: a, right: b, ..
        } = right.as_ref()
            && a.height() > b.height()
        {
            rotate_right(right);
        }
        rotate_left(root);
    }
}

fn rotate_left<T: Clone>(root: &mut Arc<Node<T>>) {
    let old = std::mem::replace(Arc::make_mut(root), Node::Leaf(Vec::new()));
    let Node::Branch { left, right, .. } = old else {
        unreachable!("rotation has branches");
    };
    let Node::Branch {
        left: middle,
        right,
        ..
    } = Arc::unwrap_or_clone(right)
    else {
        unreachable!("rotation has branches");
    };
    *Arc::make_mut(root) = Node::branch(Arc::new(Node::branch(left, middle)), right);
}

fn rotate_right<T: Clone>(root: &mut Arc<Node<T>>) {
    let old = std::mem::replace(Arc::make_mut(root), Node::Leaf(Vec::new()));
    let Node::Branch { left, right, .. } = old else {
        unreachable!("rotation has branches");
    };
    let Node::Branch {
        left,
        right: middle,
        ..
    } = Arc::unwrap_or_clone(left)
    else {
        unreachable!("rotation has branches");
    };
    *Arc::make_mut(root) = Node::branch(left, Arc::new(Node::branch(middle, right)));
}

impl<T: Clone> FromIterator<T> for Rows<T> {
    fn from_iter<I: IntoIterator<Item = T>>(rows: I) -> Self {
        let mut result = Self::default();
        for row in rows {
            result.push_back(row);
        }
        result
    }
}

impl<T> Index<usize> for Rows<T> {
    type Output = T;
    fn index(&self, index: usize) -> &T {
        self.root
            .as_ref()
            .and_then(|root| root.get(index))
            .expect("the snapshot row exists")
    }
}

#[derive(Debug)]
pub(super) struct Iter<'a, T> {
    branches: Vec<&'a Node<T>>,
    leaf: std::slice::Iter<'a, T>,
    remaining: usize,
}

impl<'a, T> Iter<'a, T> {
    fn descend(&mut self, mut node: &'a Node<T>) {
        loop {
            match node {
                Node::Leaf(rows) => {
                    self.leaf = rows.iter();
                    return;
                }
                Node::Branch { left, right, .. } => {
                    self.branches.push(right);
                    node = left;
                }
            }
        }
    }
}

impl<'a, T> Iterator for Iter<'a, T> {
    type Item = &'a T;
    fn next(&mut self) -> Option<Self::Item> {
        loop {
            if let Some(value) = self.leaf.next() {
                self.remaining -= 1;
                return Some(value);
            }
            let branch = self.branches.pop()?;
            self.descend(branch);
        }
    }
    fn size_hint(&self) -> (usize, Option<usize>) {
        (self.remaining, Some(self.remaining))
    }
}
impl<T> ExactSizeIterator for Iter<'_, T> {}

#[cfg(test)]
mod tests {
    use super::*;

    fn check<T: Clone + PartialEq + std::fmt::Debug>(rows: &Rows<T>, expected: &[T]) {
        fn node<T>(entry: &Node<T>) -> (usize, u8, usize) {
            match entry {
                Node::Leaf(rows) => {
                    assert!(rows.len() <= LEAF_CAPACITY);
                    assert!(rows.capacity() <= LEAF_CAPACITY);
                    (rows.len(), u8::from(!rows.is_empty()), 1)
                }
                Node::Branch {
                    left,
                    right,
                    len,
                    height,
                } => {
                    let (a, ah, an) = node(left);
                    let (b, bh, bn) = node(right);
                    assert!(a > 0 && b > 0);
                    assert_eq!(*len, a + b);
                    assert_eq!(*height, 1 + ah.max(bh));
                    assert!(ah.abs_diff(bh) <= 1);
                    (a + b, *height, 1 + an + bn)
                }
            }
        }
        assert_eq!(
            rows.iter().collect::<Vec<_>>(),
            expected.iter().collect::<Vec<_>>()
        );
        assert_eq!(rows.len(), expected.len());
        if let Some(root) = &rows.root {
            let (len, _, nodes) = node(root);
            assert_eq!(len, expected.len());
            assert!(nodes <= 2 * len);
        }
    }

    #[test]
    fn sequence_matches_vec_through_churn_and_old_snapshots() {
        let mut rows: Rows<_> = (0..4096).collect();
        let mut expected: Vec<_> = (0..4096).collect();
        let old = rows.clone();
        let mut seed = 17_u64;
        for i in 0..10_000 {
            seed = seed.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1);
            let index = usize::try_from(seed >> 32).unwrap() % expected.len();
            match i % 3 {
                0 => {
                    assert_eq!(rows.remove(index), expected.remove(index));
                }
                1 => {
                    rows.set(index, i);
                    expected[index] = i;
                }
                _ => {
                    rows.push_back(i);
                    expected.push(i);
                }
            }
            if i % 97 == 0 {
                check(&rows, &expected);
            }
        }
        check(&rows, &expected);
        check(&old, &(0..4096).collect::<Vec<_>>());
        while !expected.is_empty() {
            let index = expected.len() / 2;
            assert_eq!(rows.remove(index), expected.remove(index));
        }
        check(&rows, &expected);
    }

    #[test]
    fn unique_mutations_preserve_leaf_storage_and_shared_writes_are_bounded() {
        let mut rows: Rows<_> = (0..512).collect();
        let before = std::ptr::from_ref(&rows[10]);
        rows.set(10, 99);
        assert_eq!(before, std::ptr::from_ref(&rows[10]));
        let old = rows.clone();
        rows.set(10, 100);
        assert_eq!(old[10], 99);
        assert_eq!(rows[10], 100);
    }
    #[test]
    fn snapshots_copy_at_most_one_leaf_per_point_write() {
        use std::sync::atomic::{AtomicUsize, Ordering};
        #[derive(Debug)]
        struct Counted(usize, Arc<AtomicUsize>);
        impl Clone for Counted {
            fn clone(&self) -> Self {
                self.1.fetch_add(1, Ordering::Relaxed);
                Self(self.0, Arc::clone(&self.1))
            }
        }
        let clones = Arc::new(AtomicUsize::new(0));
        let mut rows: Rows<_> = (0..16_384)
            .map(|i| Counted(i, Arc::clone(&clones)))
            .collect();
        assert_eq!(clones.load(Ordering::Relaxed), 0);
        let old = rows.clone();
        assert_eq!(clones.load(Ordering::Relaxed), 0);
        rows.get_mut(8000).unwrap().0 = 77;
        assert_eq!(old[8000].0, 8000);
        assert!(clones.load(Ordering::Relaxed) <= LEAF_CAPACITY);
        clones.store(0, Ordering::Relaxed);
        rows.get_mut(8000).unwrap().0 = 78;
        assert_eq!(clones.load(Ordering::Relaxed), 0);
        drop(old);
        clones.store(0, Ordering::Relaxed);
        rows.get_mut(12_000).unwrap().0 = 79;
        assert_eq!(clones.load(Ordering::Relaxed), 0);
    }

    #[test]
    fn removed_and_replaced_values_leave_the_current_tree_immediately() {
        let removed = Arc::new(());
        let replaced = Arc::new(());
        let removed_weak = Arc::downgrade(&removed);
        let replaced_weak = Arc::downgrade(&replaced);
        let mut rows: Rows<_> = [removed, replaced].into_iter().collect();
        drop(rows.remove(0));
        assert!(removed_weak.upgrade().is_none());
        rows.set(0, Arc::new(()));
        assert!(replaced_weak.upgrade().is_none());
    }
    #[test]
    fn partial_leaf_cow_appends_keep_fixed_capacity_and_old_rows() {
        let mut rows: Rows<_> = (0..21).collect();
        let original = rows.clone();
        let mut expected: Vec<_> = (0..21).collect();
        for value in 21..34 {
            let before = rows.clone();
            let prior = expected.clone();
            rows.push_back(value);
            expected.push(value);
            check(&rows, &expected);
            check(&before, &prior);
        }
        check(&original, &(0..21).collect::<Vec<_>>());

        let mut rows: Rows<_> = (0..31).collect();
        let mut expected: Vec<_> = (0..31).collect();
        assert_eq!(rows.remove(17), expected.remove(17));
        let before = rows.clone();
        let prior = expected.clone();
        rows.push_back(99);
        expected.push(99);
        check(&rows, &expected);
        check(&before, &prior);
        rows.push_back(100);
        expected.push(100);
        check(&rows, &expected);
        check(&before, &prior);
    }
}
