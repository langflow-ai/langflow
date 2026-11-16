//! Copy-on-write rows for snapshots: a balanced tree of small leaves.
//!
//! A clone shares the root. While a clone is alive, a write copies only the
//! branches on its path and one leaf. `SnapshotList` are only appended or overwritten,
//! so the tree only ever needs a left rotation.

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
            Self::Leaf(_) => 1,
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
}

/// An ordered sequence with constant-time snapshot clones.
#[derive(Debug, Clone)]
pub(crate) struct SnapshotList<T> {
    root: Option<Arc<Node<T>>>,
}

impl<T> Default for SnapshotList<T> {
    fn default() -> Self {
        Self { root: None }
    }
}

impl<T: Clone> SnapshotList<T> {
    pub(crate) fn len(&self) -> usize {
        self.root.as_ref().map_or(0, |root| root.len())
    }

    pub(crate) fn get_mut(&mut self, index: usize) -> Option<&mut T> {
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

    pub(crate) fn set(&mut self, index: usize, value: T) {
        *self.get_mut(index).expect("the snapshot row exists") = value;
    }

    pub(crate) fn push_back(&mut self, value: T) {
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

    pub(crate) fn iter(&self) -> Iter<'_, T> {
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

/// Update the branch's length and height, and rotate it left when its right
/// side grew two levels taller than its left.
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
    if right.height() > left.height() + 1 {
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

impl<T: Clone> FromIterator<T> for SnapshotList<T> {
    fn from_iter<I: IntoIterator<Item = T>>(rows: I) -> Self {
        let mut result = Self::default();
        for row in rows {
            result.push_back(row);
        }
        result
    }
}

#[derive(Debug)]
pub(crate) struct Iter<'a, T> {
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

#[cfg(test)]
mod tests {
    use super::*;

    fn check<T: Clone + PartialEq + std::fmt::Debug>(rows: &SnapshotList<T>, expected: &[T]) {
        fn node<T>(entry: &Node<T>) -> (usize, u8, usize) {
            match entry {
                Node::Leaf(rows) => {
                    assert!(rows.len() <= LEAF_CAPACITY);
                    assert!(rows.capacity() <= LEAF_CAPACITY);
                    (rows.len(), 1, 1)
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
    fn rows_match_a_vec_through_appends_and_writes() {
        let mut rows: SnapshotList<_> = (0..4096).collect();
        let mut expected: Vec<_> = (0..4096).collect();
        let old = rows.clone();
        let mut seed = 17_u64;
        for i in 0..10_000 {
            seed = seed.wrapping_mul(6_364_136_223_846_793_005).wrapping_add(1);
            let index = usize::try_from(seed >> 32).unwrap() % expected.len();
            if i % 2 == 0 {
                rows.set(index, i);
                expected[index] = i;
            } else {
                rows.push_back(i);
                expected.push(i);
            }
            if i % 97 == 0 {
                check(&rows, &expected);
            }
        }
        check(&rows, &expected);
        check(&old, &(0..4096).collect::<Vec<_>>());
    }

    #[test]
    fn a_write_copies_nothing_without_a_clone() {
        let mut rows: SnapshotList<_> = (0..512).collect();
        let before = std::ptr::from_ref(rows.iter().nth(10).unwrap());
        rows.set(10, 99);
        assert_eq!(before, std::ptr::from_ref(rows.iter().nth(10).unwrap()));
        let old = rows.clone();
        rows.set(10, 100);
        assert_eq!(old.iter().nth(10), Some(&99));
        assert_eq!(rows.iter().nth(10), Some(&100));
    }

    #[test]
    fn a_write_copies_at_most_one_leaf_while_a_clone_lives() {
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
        let mut rows: SnapshotList<_> = (0..16_384)
            .map(|i| Counted(i, Arc::clone(&clones)))
            .collect();
        assert_eq!(clones.load(Ordering::Relaxed), 0);
        let old = rows.clone();
        assert_eq!(clones.load(Ordering::Relaxed), 0);
        rows.get_mut(8000).unwrap().0 = 77;
        assert_eq!(old.iter().nth(8000).unwrap().0, 8000);
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
    fn a_replaced_value_leaves_the_tree_at_once() {
        let replaced = Arc::new(());
        let replaced_weak = Arc::downgrade(&replaced);
        let mut rows: SnapshotList<_> = [replaced].into_iter().collect();
        rows.set(0, Arc::new(()));
        assert!(replaced_weak.upgrade().is_none());
    }

    #[test]
    fn appends_to_a_shared_leaf_keep_the_old_rows() {
        let mut rows: SnapshotList<_> = (0..21).collect();
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
    }
}
