# Feature 15: YouTube Comments Empty Fix

## Summary

Fixes a crash in the YouTube Comments component when a video has no comments (or comments are disabled). Previously, converting an empty `comments_data` list to a DataFrame and then trying to add columns and reorder would fail. Now, the code explicitly handles the empty case by creating an empty DataFrame with the correct column schema.

## Dependencies

None (no new imports or external dependencies).

## Files Changed

### `src/lfx/src/lfx/components/youtube/comments.py`

```diff
diff --git a/src/lfx/src/lfx/components/youtube/comments.py b/src/lfx/src/lfx/components/youtube/comments.py
index 68d3f5c215..8bc8926e2e 100644
--- a/src/lfx/src/lfx/components/youtube/comments.py
+++ b/src/lfx/src/lfx/components/youtube/comments.py
@@ -193,14 +193,7 @@ class YouTubeCommentsComponent(Component):
                     else:
                         request = None

-                # Convert to DataFrame
-                comments_df = pd.DataFrame(comments_data)
-
-                # Add video metadata
-                comments_df["video_id"] = video_id
-                comments_df["video_url"] = self.video_url
-
-                # Sort columns for better organization
+                # Define column order
                 column_order = [
                     "video_id",
                     "video_url",
@@ -217,7 +210,20 @@ class YouTubeCommentsComponent(Component):
                 if self.include_metrics:
                     column_order.extend(["like_count", "reply_count"])

-                comments_df = comments_df[column_order]
+                # Handle empty comments case
+                if not comments_data:
+                    # Create empty DataFrame with proper columns
+                    comments_df = pd.DataFrame(columns=column_order)
+                else:
+                    # Convert to DataFrame
+                    comments_df = pd.DataFrame(comments_data)
+
+                    # Add video metadata
+                    comments_df["video_id"] = video_id
+                    comments_df["video_url"] = self.video_url
+
+                    # Reorder columns
+                    comments_df = comments_df[column_order]

                 return DataFrame(comments_df)
```

## Implementation Notes

1. **Root cause**: When `comments_data` is empty, `pd.DataFrame(comments_data)` creates a DataFrame with no columns. Attempting to assign `comments_df["video_id"]` or reorder columns on an empty DataFrame without the expected columns would raise a `KeyError`.
2. **Fix approach**: The column order is defined first (before the branching logic). If `comments_data` is empty, an empty DataFrame is created with the correct column schema using `pd.DataFrame(columns=column_order)`. Otherwise, the original logic runs.
3. **No behavioral change for non-empty case**: When comments exist, the logic is identical -- DataFrame creation, metadata addition, column reordering.
