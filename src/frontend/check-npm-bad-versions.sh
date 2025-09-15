#!/usr/bin/env bash
set -euo pipefail

# ------------------------- CLI flags -------------------------
VERBOSE=false
SCAN=false
BASEDIR="$(pwd)"

print_usage() {
  cat <<'EOF'
Usage: check-npm-bad-versions.sh [-v] [--scan] [--basedir DIR]

Options:
  -v               Verbose: show versions and status for all modules in BAD_JSON.
  --scan           Scan the current project AND subdirectories under --basedir
                   that contain common npm dependency artifacts.
  --basedir DIR    Base directory to search when using --scan (default: CWD).
  -h, --help       Show this help.

What gets scanned:
  • Current project (CWD): installed dependencies (including all transitives).
  • Global npm install tree: installed global dependencies (checked once).
  • With --scan: additional projects found under --basedir that contain
    node_modules/, package.json, package-lock.json, or npm-shrinkwrap.json.
  • Note: this checks installed versions, not ranges declared in manifests.

Output behavior:
  • Detected bad versions are ALWAYS shown, regardless of options.
  • With --scan -v: the script also prints which scanner methods ran and the
    deduplicated list of project directories it will scan.

Exit status:
  Exit code equals the number of bad versions detected (capped at 255).

Examples:
  # Scan only the current project
  ./check-npm-bad-versions.sh

  # Verbose scan of current project (show all modules and versions)
  ./check-npm-bad-versions.sh -v

  # Recursively scan all subprojects under /path/to/repos and show scanners used
  ./check-npm-bad-versions.sh --scan --basedir /path/to/repos -v

Sample minimal output (bad versions found):
  == Project: /my-app
  ⟶ debug
     local : 4.4.2
     global: not found
     ⚠ bad present: 4.4.2

  Detected bad versions: local=1, global=0, total=1

Sample verbose output (no bad versions):
  == Project: /my-app
  ⟶ chalk
     local : 5.6.1
     global: not found
     bad present: none

  Detected bad versions: local=0, global=0, total=0
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    -v) VERBOSE=true; shift ;;
    --scan) SCAN=true; shift ;;
    --basedir)
      if [ "$#" -lt 2 ]; then echo "Missing value for --basedir" >&2; exit 2; fi
      BASEDIR="$2"; shift 2 ;;
    -h|--help) print_usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; print_usage; exit 2 ;;
  esac
done

# ---------------- Known-bad versions per module ----------------
BAD_JSON='{
  "ansi-styles": ["6.2.2"],
  "debug": ["4.4.2"],
  "chalk": ["5.6.1"],
  "supports-color": ["10.2.1"],
  "strip-ansi": ["7.1.1"],
  "ansi-regex": ["6.2.1"],
  "wrap-ansi": ["9.0.1"],
  "color-convert": ["3.1.1"],
  "color-name": ["2.0.1"],
  "is-arrayish": ["0.3.3"],
  "slice-ansi": ["7.1.1"],
  "color": ["5.0.1"],
  "color-string": ["2.1.1"],
  "simple-swizzle": ["0.2.3"],
  "supports-hyperlinks": ["4.1.1"],
  "has-ansi": ["6.0.1"],
  "chalk-template": ["1.1.1"],
  "backslash": ["0.2.1"],
  "error-ex": []
}'

# ------------- jq helper: collect versions for a name -------------
jq_find_versions='
  def walkentries:
    (.dependencies // {} | to_entries[] | (. , (.value | walkentries))) // empty;
  [ walkentries
    | select(.key == $name)
    | .value.version
  ]
  | map(select(. != null))
  | unique
'

# ---------------- Project scanners (each encapsulated) ----------------
find_projects_via_node_modules() {
  find "$1" -type d -name node_modules -prune -print 2>/dev/null \
    | sed 's:/node_modules$::'
}
find_projects_via_package_json() {
  find "$1" -type f -name package.json -not -path '*/node_modules/*' -print 2>/dev/null \
    | sed 's:/package.json$::'
}
find_projects_via_package_lock() {
  find "$1" -type f -name package-lock.json -not -path '*/node_modules/*' -print 2>/dev/null \
    | sed 's:/package-lock.json$::'
}
find_projects_via_shrinkwrap() {
  find "$1" -type f -name npm-shrinkwrap.json -not -path '*/node_modules/*' -print 2>/dev/null \
    | sed 's:/npm-shrinkwrap.json$::'
}

# ---------------- Gather project directories ----------------
projects_tmp="$(mktemp)"
printf '%s\n' "$(pwd)" > "$projects_tmp"

# If --scan is set, run scanners; only print scanner info when --scan -v
nm_tmp=""
pj_tmp=""
pl_tmp=""
sw_tmp=""

if $SCAN; then
  if [ ! -d "$BASEDIR" ]; then
    echo "basedir not found: $BASEDIR" >&2
    rm -f "$projects_tmp"
    exit 2
  fi

  nm_tmp="$(mktemp)"
  pj_tmp="$(mktemp)"
  pl_tmp="$(mktemp)"
  sw_tmp="$(mktemp)"

  find_projects_via_node_modules "$BASEDIR" > "$nm_tmp"
  find_projects_via_package_json "$BASEDIR"  > "$pj_tmp"
  find_projects_via_package_lock "$BASEDIR"  > "$pl_tmp"
  find_projects_via_shrinkwrap "$BASEDIR"    > "$sw_tmp"

  # Aggregate (always, regardless of verbosity)
  cat "$nm_tmp" "$pj_tmp" "$pl_tmp" "$sw_tmp" >> "$projects_tmp"
fi

projects_uniq="$(mktemp)"
sort "$projects_tmp" | uniq > "$projects_uniq"
rm -f "$projects_tmp"

# If both --scan and -v, show scanner methods + deduped list
if $SCAN && $VERBOSE; then
  echo "== Scanner methods used =="
  if [ -n "$nm_tmp" ] && [ -f "$nm_tmp" ]; then printf 'node_modules      : %s\n' "$(wc -l < "$nm_tmp" | tr -d ' ')"; fi
  if [ -n "$pj_tmp" ] && [ -f "$pj_tmp" ]; then printf 'package.json      : %s\n' "$(wc -l < "$pj_tmp" | tr -d ' ')"; fi
  if [ -n "$pl_tmp" ] && [ -f "$pl_tmp" ]; then printf 'package-lock.json : %s\n' "$(wc -l < "$pl_tmp" | tr -d ' ')"; fi
  if [ -n "$sw_tmp" ] && [ -f "$sw_tmp" ]; then printf 'npm-shrinkwrap    : %s\n' "$(wc -l < "$sw_tmp" | tr -d ' ')"; fi
  echo "=========================="
  echo "== Found project directories (deduped) =="
  cat "$projects_uniq"
  echo "========================================="
fi

# Clean up scanner tmp files (after optional print)
if [ -n "$nm_tmp" ]; then rm -f "$nm_tmp" || true; fi
if [ -n "$pj_tmp" ]; then rm -f "$pj_tmp" || true; fi
if [ -n "$pl_tmp" ]; then rm -f "$pl_tmp" || true; fi
if [ -n "$sw_tmp" ]; then rm -f "$sw_tmp" || true; fi

# ---------------- Build global tree once ----------------
global_tree="$(npm ls -g --all --json 2>/dev/null || echo '{}')"

# ---------------- Collect module keys (skip empty bad lists) ----------------
modules_tmp="$(mktemp)"
printf '%s' "$BAD_JSON" | jq -r 'to_entries[] | select((.value|length)>0) | .key' > "$modules_tmp"

# ---------------- Scan function ----------------
scan_project() {
  project_dir="$1"
  if [ -d "$project_dir" ]; then
    project_tree="$( (cd "$project_dir" && npm ls --all --json 2>/dev/null) || echo '{}' )"
  else
    project_tree='{}'
  fi

  results='[]'
  while IFS= read -r name || [ -n "$name" ]; do
    [ -n "$name" ] || continue
    local_json="$(jq -c --arg name "$name" "$jq_find_versions" <<<"$project_tree" 2>/dev/null || echo '[]')"
    global_json="$(jq -c --arg name "$name" "$jq_find_versions" <<<"$global_tree" 2>/dev/null || echo '[]')"
    bad_list_json="$(jq -c --arg name "$name" '.[$name] // []' <<<"$BAD_JSON")"
    bad_present_local="$(jq -c --argjson found "$local_json" --argjson bad "$bad_list_json" -n '[ ($found // [])[] as $v | select( ($bad // []) | index($v) != null ) ] | unique')"
    bad_present_global="$(jq -c --argjson found "$global_json" --argjson bad "$bad_list_json" -n '[ ($found // [])[] as $v | select( ($bad // []) | index($v) != null ) ] | unique')"
    obj="$(jq -c \
      --arg project "$project_dir" \
      --arg name "$name" \
      --argjson local "$local_json" \
      --argjson global "$global_json" \
      --argjson bad "$bad_list_json" \
      --argjson bad_local "$bad_present_local" \
      --argjson bad_global "$bad_present_global" -n '{
        project: $project,
        name: $name,
        local: $local,
        global: $global,
        known_bad: $bad,
        bad_present_local: $bad_local,
        bad_present_global: $bad_global
      }')"
    results="$(jq -c --argjson obj "$obj" '. + [$obj]' <<<"$results")"
  done < "$modules_tmp"
  printf '%s' "$results"
}

# ---------------- Run scans ----------------
all_results='[]'
while IFS= read -r proj || [ -n "$proj" ]; do
  [ -n "$proj" ] || continue
  proj_results="$(scan_project "$proj")"
  all_results="$(jq -c --argjson r "$proj_results" '. + $r' <<<"$all_results")"
done < "$projects_uniq"
rm -f "$projects_uniq" "$modules_tmp"

# ---------------- Summaries & exit status ----------------
local_impacted="$(jq -r '[ .[] | (.bad_present_local | length) ] | add // 0' <<<"$all_results")"
# FIX: sort before group_by to avoid spurious counts
global_impacted="$(jq -r 'sort_by(.name) | group_by(.name) | map( [ .[].bad_present_global[]? ] | unique | length ) | add // 0' <<<"$all_results")"
total_impacted=$(( local_impacted + global_impacted ))
exit_status=$(( total_impacted > 255 ? 255 : total_impacted ))

# --------- Output ----------
# Always show detected bad versions (minimal mode prints only impacted)
impacted="$(jq -c '[ .[] | select((.bad_present_local|length>0) or (.bad_present_global|length>0)) ]' <<<"$all_results")"

if [ "$(jq -r 'length' <<<"$impacted")" -gt 0 ]; then
  jq -r '
    sort_by(.project, .name)
    | group_by(.project)[]
    | "== Project: \([.[0].project])\n"
    + ( .[]
        | select((.bad_present_local|length>0) or (.bad_present_global|length>0))
        | "⟶ \(.name)\n"
        + "   local : " + (if (.local|length)>0 then (.local|join(" ")) else "not found" end) + "\n"
        + "   global: " + (if (.global|length)>0 then (.global|join(" ")) else "not found" end) + "\n"
        + "   ⚠ bad present: "
          + ( ( ( .bad_present_local // [] ) + ( .bad_present_global // [] ) ) | unique | join(" ") )
          + "\n\n"
      | .
      )
  ' <<<"$impacted"
fi

# If verbose, also show full status for all modules (even if none are bad)
if $VERBOSE; then
  jq -r '
    sort_by(.project, .name)
    | group_by(.project)[]
    | "== Project: \([.[0].project])\n"
    + ( .[]
        | "⟶ \(.name)\n"
        + "   local : " + (if (.local|length)>0 then (.local|join(" ")) else "not found" end) + "\n"
        + "   global: " + (if (.global|length)>0 then (.global|join(" ")) else "not found" end) + "\n"
        + ( if ((.bad_present_local|length) + (.bad_present_global|length))>0
            then "   ⚠ bad present: "
                 + ( ( ( .bad_present_local // [] ) + ( .bad_present_global // [] ) ) | unique | join(" ") )
                 + "\n"
            else "   bad present: none\n"
          end
        ) + "\n"
      | .
      )
  ' <<<"$all_results"
fi

echo "Detected bad versions: local=$local_impacted, global=$global_impacted, total=$total_impacted"
exit "$exit_status"

