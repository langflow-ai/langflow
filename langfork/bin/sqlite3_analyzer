#! /bin/sh
# restart with tclsh \
exec tclsh "$0" ${1+"$@"}
package require sqlite3

# Run this TCL script using an SQLite-enabled TCL interpreter to get a report
# on how much disk space is used by a particular data to actually store data
# versus how much space is unused.
#
# The dbstat virtual table is required.
#

if {[catch {

# Argument $tname is the name of a table within the database opened by
# database handle [db]. Return true if it is a WITHOUT ROWID table, or
# false otherwise.
#
proc is_without_rowid {tname} {
  set t [string map {' ''} $tname]
  db eval "PRAGMA index_list = '$t'" o {
    if {$o(origin) == "pk"} {
      set n $o(name)
      if {0==[db one { SELECT count(*) FROM sqlite_schema WHERE name=$n }]} {
        return 1
      }
    }
  }
  return 0
}

# Read and run TCL commands from standard input.  Used to implement
# the --tclsh option.
#
proc tclsh {} {
  set line {}
  while {![eof stdin]} {
    if {$line!=""} {
      puts -nonewline "> "
    } else {
      puts -nonewline "% "
    }
    flush stdout
    append line [gets stdin]
    if {[info complete $line]} {
      if {[catch {uplevel #0 $line} result]} {
        puts stderr "Error: $result"
      } elseif {$result!=""} {
        puts $result
      }
      set line {}
    } else {
      append line \n
    }
  }
}


# Get the name of the database to analyze
#
proc usage {} {
  set argv0 [file rootname [file tail [info script]]]
  puts stderr "Usage: $argv0 ?--pageinfo? ?--stats? database-filename"
  puts stderr {
Analyze the SQLite3 database file specified by the "database-filename"
argument and output a report detailing size and storage efficiency
information for the database and its constituent tables and indexes.

Options:

   --pageinfo   Show how each page of the database-file is used

   --stats      Output SQL text that creates a new database containing
                statistics about the database that was analyzed

   --tclsh      Run the built-in TCL interpreter interactively (for debugging)

   --version    Show the version number of SQLite
}
  exit 1
}
set file_to_analyze {}
set flags(-pageinfo) 0
set flags(-stats) 0
set flags(-debug) 0
append argv {}
foreach arg $argv {
  if {[regexp {^-+pageinfo$} $arg]} {
    set flags(-pageinfo) 1
  } elseif {[regexp {^-+stats$} $arg]} {
    set flags(-stats) 1
  } elseif {[regexp {^-+debug$} $arg]} {
    set flags(-debug) 1
  } elseif {[regexp {^-+tclsh$} $arg]} {
    tclsh
    exit 0
  } elseif {[regexp {^-+version$} $arg]} {
    sqlite3 mem :memory:
    puts [mem one {SELECT sqlite_version()||' '||sqlite_source_id()}]
    mem close
    exit 0
  } elseif {[regexp {^-} $arg]} {
    puts stderr "Unknown option: $arg"
    usage
  } elseif {$file_to_analyze!=""} {
    usage
  } else {
    set file_to_analyze $arg
  }
}
if {$file_to_analyze==""} usage
set root_filename $file_to_analyze
regexp {^file:(//)?([^?]*)} $file_to_analyze all x1 root_filename
if {![file exists $root_filename]} {
  puts stderr "No such file: $root_filename"
  exit 1
}
if {![file readable $root_filename]} {
  puts stderr "File is not readable: $root_filename"
  exit 1
}
set true_file_size [file size $root_filename]
if {$true_file_size<512} {
  puts stderr "Empty or malformed database: $root_filename"
  exit 1
}

# Compute the total file size assuming test_multiplexor is being used.
# Assume that SQLITE_ENABLE_8_3_NAMES might be enabled
#
set extension [file extension $root_filename]
set pattern $root_filename
append pattern {[0-3][0-9][0-9]}
foreach f [glob -nocomplain $pattern] {
  incr true_file_size [file size $f]
  set extension {}
}
if {[string length $extension]>=2 && [string length $extension]<=4} {
  set pattern [file rootname $root_filename]
  append pattern {.[0-3][0-9][0-9]}
  foreach f [glob -nocomplain $pattern] {
    incr true_file_size [file size $f]
  }
}

# Open the database
#
if {[catch {sqlite3 db $file_to_analyze -uri 1} msg]} {
  puts stderr "error trying to open $file_to_analyze: $msg"
  exit 1
}
if {$flags(-debug)} {
  proc dbtrace {txt} {puts $txt; flush stdout;}
  db trace ::dbtrace
}

# Make sure all required compile-time options are available
#
if {![db exists {SELECT 1 FROM pragma_compile_options
                WHERE compile_options='ENABLE_DBSTAT_VTAB'}]} {
  puts "The SQLite database engine linked with this application\
        lacks required capabilities. Recompile using the\
        -DSQLITE_ENABLE_DBSTAT_VTAB compile-time option to fix\
        this problem."
  exit 1
}

db eval {SELECT count(*) FROM sqlite_schema}
set pageSize [expr {wide([db one {PRAGMA page_size}])}]

if {$flags(-pageinfo)} {
  db eval {CREATE VIRTUAL TABLE temp.stat USING dbstat}
  db eval {SELECT name, path, pageno FROM temp.stat ORDER BY pageno} {
    puts "$pageno $name $path"
  }
  exit 0
}
if {$flags(-stats)} {
  db eval {CREATE VIRTUAL TABLE temp.stat USING dbstat}
  puts "BEGIN;"
  puts "CREATE TABLE stats("
  puts "  name       STRING,           /* Name of table or index */"
  puts "  path       INTEGER,          /* Path to page from root */"
  puts "  pageno     INTEGER,          /* Page number */"
  puts "  pagetype   STRING,           /* 'internal', 'leaf' or 'overflow' */"
  puts "  ncell      INTEGER,          /* Cells on page (0 for overflow) */"
  puts "  payload    INTEGER,          /* Bytes of payload on this page */"
  puts "  unused     INTEGER,          /* Bytes of unused space on this page */"
  puts "  mx_payload INTEGER,          /* Largest payload size of all cells */"
  puts "  pgoffset   INTEGER,          /* Offset of page in file */"
  puts "  pgsize     INTEGER           /* Size of the page */"
  puts ");"
  db eval {SELECT quote(name) || ',' ||
                  quote(path) || ',' ||
                  quote(pageno) || ',' ||
                  quote(pagetype) || ',' ||
                  quote(ncell) || ',' ||
                  quote(payload) || ',' ||
                  quote(unused) || ',' ||
                  quote(mx_payload) || ',' ||
                  quote(pgoffset) || ',' ||
                  quote(pgsize) AS x FROM stat} {
    puts "INSERT INTO stats VALUES($x);"
  }
  puts "COMMIT;"
  exit 0
}


# In-memory database for collecting statistics. This script loops through
# the tables and indices in the database being analyzed, adding a row for each
# to an in-memory database (for which the schema is shown below). It then
# queries the in-memory db to produce the space-analysis report.
#
sqlite3 mem :memory:
if {$flags(-debug)} {
  proc dbtrace {txt} {puts $txt; flush stdout;}
  mem trace ::dbtrace
}
set tabledef {CREATE TABLE space_used(
   name clob,        -- Name of a table or index in the database file
   tblname clob,     -- Name of associated table
   is_index boolean, -- TRUE if it is an index, false for a table
   is_without_rowid boolean, -- TRUE if WITHOUT ROWID table  
   nentry int,       -- Number of entries in the BTree
   leaf_entries int, -- Number of leaf entries
   depth int,        -- Depth of the b-tree
   payload int,      -- Total amount of data stored in this table or index
   ovfl_payload int, -- Total amount of data stored on overflow pages
   ovfl_cnt int,     -- Number of entries that use overflow
   mx_payload int,   -- Maximum payload size
   int_pages int,    -- Number of interior pages used
   leaf_pages int,   -- Number of leaf pages used
   ovfl_pages int,   -- Number of overflow pages used
   int_unused int,   -- Number of unused bytes on interior pages
   leaf_unused int,  -- Number of unused bytes on primary pages
   ovfl_unused int,  -- Number of unused bytes on overflow pages
   gap_cnt int,      -- Number of gaps in the page layout
   compressed_size int  -- Total bytes stored on disk
);}
mem eval $tabledef

# Create a temporary "dbstat" virtual table.
#
db eval {CREATE VIRTUAL TABLE temp.stat USING dbstat}
db eval {CREATE TEMP TABLE dbstat AS SELECT * FROM temp.stat
         ORDER BY name, path}
db eval {DROP TABLE temp.stat}

set isCompressed 0
set compressOverhead 0
set depth 0
set sql { SELECT name, tbl_name FROM sqlite_schema WHERE rootpage>0 }
foreach {name tblname} [concat sqlite_schema sqlite_schema [db eval $sql]] {

  set is_index [expr {$name!=$tblname}]
  set is_without_rowid [is_without_rowid $name]
  db eval {
    SELECT 
      sum(ncell) AS nentry,
      sum((pagetype=='leaf')*ncell) AS leaf_entries,
      sum(payload) AS payload,
      sum((pagetype=='overflow') * payload) AS ovfl_payload,
      sum(path LIKE '%+000000') AS ovfl_cnt,
      max(mx_payload) AS mx_payload,
      sum(pagetype=='internal') AS int_pages,
      sum(pagetype=='leaf') AS leaf_pages,
      sum(pagetype=='overflow') AS ovfl_pages,
      sum((pagetype=='internal') * unused) AS int_unused,
      sum((pagetype=='leaf') * unused) AS leaf_unused,
      sum((pagetype=='overflow') * unused) AS ovfl_unused,
      sum(pgsize) AS compressed_size,
      max((length(CASE WHEN path LIKE '%+%' THEN '' ELSE path END)+3)/4)
        AS depth
    FROM temp.dbstat WHERE name = $name
  } break

  set total_pages [expr {$leaf_pages+$int_pages+$ovfl_pages}]
  set storage [expr {$total_pages*$pageSize}]
  if {!$isCompressed && $storage>$compressed_size} {
    set isCompressed 1
    set compressOverhead 14
  }

  # Column 'gap_cnt' is set to the number of non-contiguous entries in the
  # list of pages visited if the b-tree structure is traversed in a top-down
  # fashion (each node visited before its child-tree is passed). Any overflow
  # chains present are traversed from start to finish before any child-tree
  # is.
  #
  set gap_cnt 0
  set prev 0
  db eval {
    SELECT pageno, pagetype FROM temp.dbstat
     WHERE name=$name
     ORDER BY pageno
  } {
    if {$prev>0 && $pagetype=="leaf" && $pageno!=$prev+1} {
      incr gap_cnt
    }
    set prev $pageno
  }
  mem eval {
    INSERT INTO space_used VALUES(
      $name,
      $tblname,
      $is_index,
      $is_without_rowid,
      $nentry,
      $leaf_entries,
      $depth,
      $payload,     
      $ovfl_payload,
      $ovfl_cnt,   
      $mx_payload,
      $int_pages,
      $leaf_pages,  
      $ovfl_pages, 
      $int_unused, 
      $leaf_unused,
      $ovfl_unused,
      $gap_cnt,
      $compressed_size
    );
  }
}

proc integerify {real} {
  if {[string is double -strict $real]} {
    return [expr {wide($real)}]
  } else {
    return 0
  }
}
mem function int integerify

# Quote a string for use in an SQL query. Examples:
#
# [quote {hello world}]   == {'hello world'}
# [quote {hello world's}] == {'hello world''s'}
#
proc quote {txt} {
  return [string map {' ''} $txt]
}

# Output a title line
#
proc titleline {title} {
  if {$title==""} {
    puts [string repeat * 79]
  } else {
    set len [string length $title]
    set stars [string repeat * [expr {79-$len-5}]]
    puts "*** $title $stars"
  }
}

# Generate a single line of output in the statistics section of the
# report.
#
proc statline {title value {extra {}}} {
  set len [string length $title]
  set dots [string repeat . [expr {50-$len}]]
  set len [string length $value]
  set sp2 [string range {          } $len end]
  if {$extra ne ""} {
    set extra " $extra"
  }
  puts "$title$dots $value$sp2$extra"
}

# Generate a formatted percentage value for $num/$denom
#
proc percent {num denom {of {}}} {
  if {$denom==0.0} {return ""}
  set v [expr {$num*100.0/$denom}]
  set of {}
  if {$v==100.0 || $v<0.001 || ($v>1.0 && $v<99.0)} {
    return [format {%5.1f%% %s} $v $of]
  } elseif {$v<0.1 || $v>99.9} {
    return [format {%7.3f%% %s} $v $of]
  } else {
    return [format {%6.2f%% %s} $v $of]
  }
}

proc divide {num denom} {
  if {$denom==0} {return 0.0}
  return [format %.2f [expr {double($num)/double($denom)}]]
}

# Generate a subreport that covers some subset of the database.
# the $where clause determines which subset to analyze.
#
proc subreport {title where showFrag} {
  global pageSize file_pgcnt compressOverhead

  # Query the in-memory database for the sum of various statistics 
  # for the subset of tables/indices identified by the WHERE clause in
  # $where. Note that even if the WHERE clause matches no rows, the
  # following query returns exactly one row (because it is an aggregate).
  #
  # The results of the query are stored directly by SQLite into local 
  # variables (i.e. $nentry, $payload etc.).
  #
  mem eval "
    SELECT
      int(sum(
        CASE WHEN (is_without_rowid OR is_index) THEN nentry 
             ELSE leaf_entries 
        END
      )) AS nentry,
      int(sum(payload)) AS payload,
      int(sum(ovfl_payload)) AS ovfl_payload,
      max(mx_payload) AS mx_payload,
      int(sum(ovfl_cnt)) as ovfl_cnt,
      int(sum(leaf_pages)) AS leaf_pages,
      int(sum(int_pages)) AS int_pages,
      int(sum(ovfl_pages)) AS ovfl_pages,
      int(sum(leaf_unused)) AS leaf_unused,
      int(sum(int_unused)) AS int_unused,
      int(sum(ovfl_unused)) AS ovfl_unused,
      int(sum(gap_cnt)) AS gap_cnt,
      int(sum(compressed_size)) AS compressed_size,
      int(max(depth)) AS depth,
      count(*) AS cnt
    FROM space_used WHERE $where" {} {}

  # Output the sub-report title, nicely decorated with * characters.
  #
  puts ""
  titleline $title
  puts ""

  # Calculate statistics and store the results in TCL variables, as follows:
  #
  # total_pages: Database pages consumed.
  # total_pages_percent: Pages consumed as a percentage of the file.
  # storage: Bytes consumed.
  # payload_percent: Payload bytes used as a percentage of $storage.
  # total_unused: Unused bytes on pages.
  # avg_payload: Average payload per btree entry.
  # avg_fanout: Average fanout for internal pages.
  # avg_unused: Average unused bytes per btree entry.
  # avg_meta: Average metadata overhead per entry.
  # ovfl_cnt_percent: Percentage of btree entries that use overflow pages.
  #
  set total_pages [expr {$leaf_pages+$int_pages+$ovfl_pages}]
  set total_pages_percent [percent $total_pages $file_pgcnt]
  set storage [expr {$total_pages*$pageSize}]
  set payload_percent [percent $payload $storage {of storage consumed}]
  set total_unused [expr {$ovfl_unused+$int_unused+$leaf_unused}]
  set avg_payload [divide $payload $nentry]
  set avg_unused [divide $total_unused $nentry]
  set total_meta [expr {$storage - $payload - $total_unused}]
  set total_meta [expr {$total_meta + 4*($ovfl_pages - $ovfl_cnt)}]
  set meta_percent [percent $total_meta $storage {of metadata}]
  set avg_meta [divide $total_meta $nentry]
  if {$int_pages>0} {
    # TODO: Is this formula correct?
    set nTab [mem eval "
      SELECT count(*) FROM (
          SELECT DISTINCT tblname FROM space_used WHERE $where AND is_index=0
      )
    "]
    set avg_fanout [mem eval "
      SELECT (sum(leaf_pages+int_pages)-$nTab)/sum(int_pages) FROM space_used
          WHERE $where
    "]
    set avg_fanout [format %.2f $avg_fanout]
  }
  set ovfl_cnt_percent [percent $ovfl_cnt $nentry {of all entries}]

  # Print out the sub-report statistics.
  #
  statline {Percentage of total database} $total_pages_percent
  statline {Number of entries} $nentry
  statline {Bytes of storage consumed} $storage
  if {$compressed_size!=$storage} {
    set compressed_size [expr {$compressed_size+$compressOverhead*$total_pages}]
    set pct [expr {$compressed_size*100.0/$storage}]
    set pct [format {%5.1f%%} $pct]
    statline {Bytes used after compression} $compressed_size $pct
  }
  statline {Bytes of payload} $payload $payload_percent
  statline {Bytes of metadata} $total_meta $meta_percent
  if {$cnt==1} {statline {B-tree depth} $depth}
  statline {Average payload per entry} $avg_payload
  statline {Average unused bytes per entry} $avg_unused
  statline {Average metadata per entry} $avg_meta
  if {[info exists avg_fanout]} {
    statline {Average fanout} $avg_fanout
  }
  if {$showFrag && $total_pages>1} {
    set fragmentation [percent $gap_cnt [expr {$total_pages-1}]]
    statline {Non-sequential pages} $gap_cnt $fragmentation
  }
  statline {Maximum payload per entry} $mx_payload
  statline {Entries that use overflow} $ovfl_cnt $ovfl_cnt_percent
  if {$int_pages>0} {
    statline {Index pages used} $int_pages
  }
  statline {Primary pages used} $leaf_pages
  statline {Overflow pages used} $ovfl_pages
  statline {Total pages used} $total_pages
  if {$int_unused>0} {
    set int_unused_percent [
         percent $int_unused [expr {$int_pages*$pageSize}] {of index space}]
    statline "Unused bytes on index pages" $int_unused $int_unused_percent
  }
  statline "Unused bytes on primary pages" $leaf_unused [
     percent $leaf_unused [expr {$leaf_pages*$pageSize}] {of primary space}]
  statline "Unused bytes on overflow pages" $ovfl_unused [
     percent $ovfl_unused [expr {$ovfl_pages*$pageSize}] {of overflow space}]
  statline "Unused bytes on all pages" $total_unused [
               percent $total_unused $storage {of all space}]
  return 1
}

# Calculate the overhead in pages caused by auto-vacuum. 
#
# This procedure calculates and returns the number of pages used by the 
# auto-vacuum 'pointer-map'. If the database does not support auto-vacuum,
# then 0 is returned. The two arguments are the size of the database file in
# pages and the page size used by the database (in bytes).
proc autovacuum_overhead {filePages pageSize} {

  # Set $autovacuum to non-zero for databases that support auto-vacuum.
  set autovacuum [db one {PRAGMA auto_vacuum}]

  # If the database is not an auto-vacuum database or the file consists
  # of one page only then there is no overhead for auto-vacuum. Return zero.
  if {0==$autovacuum || $filePages==1} {
    return 0
  }

  # The number of entries on each pointer map page. The layout of the
  # database file is one pointer-map page, followed by $ptrsPerPage other
  # pages, followed by a pointer-map page etc. The first pointer-map page
  # is the second page of the file overall.
  set ptrsPerPage [expr {double($pageSize/5)}]

  # Return the number of pointer map pages in the database.
  return [expr {wide(ceil(($filePages-1.0)/($ptrsPerPage+1.0)))}]
}


# Calculate the summary statistics for the database and store the results
# in TCL variables. They are output below. Variables are as follows:
#
# pageSize:      Size of each page in bytes.
# file_bytes:    File size in bytes.
# file_pgcnt:    Number of pages in the file.
# file_pgcnt2:   Number of pages in the file (calculated).
# av_pgcnt:      Pages consumed by the auto-vacuum pointer-map.
# av_percent:    Percentage of the file consumed by auto-vacuum pointer-map.
# inuse_pgcnt:   Data pages in the file.
# inuse_percent: Percentage of pages used to store data.
# free_pgcnt:    Free pages calculated as (<total pages> - <in-use pages>)
# free_pgcnt2:   Free pages in the file according to the file header.
# free_percent:  Percentage of file consumed by free pages (calculated).
# free_percent2: Percentage of file consumed by free pages (header).
# ntable:        Number of tables in the db.
# nindex:        Number of indices in the db.
# nautoindex:    Number of indices created automatically.
# nmanindex:     Number of indices created manually.
# user_payload:  Number of bytes of payload in table btrees 
#                (not including sqlite_schema)
# user_percent:  $user_payload as a percentage of total file size.

### The following, setting $file_bytes based on the actual size of the file
### on disk, causes this tool to choke on zipvfs databases. So set it based
### on the return of [PRAGMA page_count] instead.
if 0 {
  set file_bytes  [file size $file_to_analyze]
  set file_pgcnt  [expr {$file_bytes/$pageSize}]
}
set file_pgcnt  [db one {PRAGMA page_count}]
set file_bytes  [expr {$file_pgcnt * $pageSize}]

set av_pgcnt    [autovacuum_overhead $file_pgcnt $pageSize]
set av_percent  [percent $av_pgcnt $file_pgcnt]

set sql {SELECT sum(leaf_pages+int_pages+ovfl_pages) FROM space_used}
set inuse_pgcnt   [expr {wide([mem eval $sql])}]
set inuse_percent [percent $inuse_pgcnt $file_pgcnt]

set free_pgcnt    [expr {$file_pgcnt-$inuse_pgcnt-$av_pgcnt}]
set free_percent  [percent $free_pgcnt $file_pgcnt]
set free_pgcnt2   [db one {PRAGMA freelist_count}]
set free_percent2 [percent $free_pgcnt2 $file_pgcnt]

set file_pgcnt2 [expr {$inuse_pgcnt+$free_pgcnt2+$av_pgcnt}]

# Account for the lockbyte page
if {$file_pgcnt2*$pageSize>1073742335} {incr file_pgcnt2}

set ntable [db eval {SELECT count(*)+1 FROM sqlite_schema WHERE type='table'}]
set nindex [db eval {SELECT count(*) FROM sqlite_schema WHERE type='index'}]
set sql {SELECT count(*) FROM sqlite_schema WHERE name LIKE 'sqlite_autoindex%'}
set nautoindex [db eval $sql]
set nmanindex [expr {$nindex-$nautoindex}]

# set total_payload [mem eval "SELECT sum(payload) FROM space_used"]
set user_payload [mem one {SELECT int(sum(payload)) FROM space_used
     WHERE NOT is_index AND name NOT LIKE 'sqlite_schema'}]
set user_percent [percent $user_payload $file_bytes]

# Output the summary statistics calculated above.
#
puts "/** Disk-Space Utilization Report For $root_filename"
puts ""
statline {Page size in bytes} $pageSize
statline {Pages in the whole file (measured)} $file_pgcnt
statline {Pages in the whole file (calculated)} $file_pgcnt2
statline {Pages that store data} $inuse_pgcnt $inuse_percent
statline {Pages on the freelist (per header)} $free_pgcnt2 $free_percent2
statline {Pages on the freelist (calculated)} $free_pgcnt $free_percent
statline {Pages of auto-vacuum overhead} $av_pgcnt $av_percent
statline {Number of tables in the database} $ntable
statline {Number of indices} $nindex
statline {Number of defined indices} $nmanindex
statline {Number of implied indices} $nautoindex
if {$isCompressed} {
  statline {Size of uncompressed content in bytes} $file_bytes
  set efficiency [percent $true_file_size $file_bytes]
  statline {Size of compressed file on disk} $true_file_size $efficiency
} else {
  statline {Size of the file in bytes} $file_bytes
}
statline {Bytes of user payload stored} $user_payload $user_percent

# Output table rankings
#
puts ""
titleline "Page counts for all tables with their indices"
puts ""
mem eval {SELECT tblname, count(*) AS cnt, 
              int(sum(int_pages+leaf_pages+ovfl_pages)) AS size
          FROM space_used GROUP BY tblname ORDER BY size+0 DESC, tblname} {} {
  statline [string toupper $tblname] $size [percent $size $file_pgcnt]
}
puts ""
titleline "Page counts for all tables and indices separately"
puts ""
mem eval {
  SELECT
       upper(name) AS nm,
       int(int_pages+leaf_pages+ovfl_pages) AS size
    FROM space_used
   ORDER BY size+0 DESC, name} {} {
  statline $nm $size [percent $size $file_pgcnt]
}
if {$isCompressed} {
  puts ""
  titleline "Bytes of disk space used after compression"
  puts ""
  set csum 0
  mem eval {SELECT tblname,
                  int(sum(compressed_size)) +
                         $compressOverhead*sum(int_pages+leaf_pages+ovfl_pages)
                        AS csize
          FROM space_used GROUP BY tblname ORDER BY csize+0 DESC, tblname} {} {
    incr csum $csize
    statline [string toupper $tblname] $csize [percent $csize $true_file_size]
  }
  set overhead [expr {$true_file_size - $csum}]
  if {$overhead>0} {
    statline {Header and free space} $overhead [percent $overhead $true_file_size]
  }
}

# Output subreports
#
if {$nindex>0} {
  subreport {All tables and indices} 1 0
}
subreport {All tables} {NOT is_index} 0
if {$nindex>0} {
  subreport {All indices} {is_index} 0
}
foreach tbl [mem eval {SELECT DISTINCT tblname name FROM space_used
                       ORDER BY name}] {
  set qn [quote $tbl]
  set name [string toupper $tbl]
  set n [mem eval {SELECT count(*) FROM space_used WHERE tblname=$tbl}]
  if {$n>1} {
    set idxlist [mem eval "SELECT name FROM space_used
                            WHERE tblname='$qn' AND is_index
                            ORDER BY 1"]
    subreport "Table $name and all its indices" "tblname='$qn'" 0
    subreport "Table $name w/o any indices" "name='$qn'" 1
    if {[llength $idxlist]>1} {
      subreport "Indices of table $name" "tblname='$qn' AND is_index" 0
    }
    foreach idx $idxlist {
      set qidx [quote $idx]
      subreport "Index [string toupper $idx] of table $name" "name='$qidx'" 1
    }
  } else {
    subreport "Table $name" "name='$qn'" 1
  }
}

# Output instructions on what the numbers above mean.
#
puts ""
titleline Definitions
puts {
Page size in bytes

    The number of bytes in a single page of the database file.  
    Usually 1024.

Number of pages in the whole file
}
puts "    The number of $pageSize-byte pages that go into forming the complete
    database"
puts {
Pages that store data

    The number of pages that store data, either as primary B*Tree pages or
    as overflow pages.  The number at the right is the data pages divided by
    the total number of pages in the file.

Pages on the freelist

    The number of pages that are not currently in use but are reserved for
    future use.  The percentage at the right is the number of freelist pages
    divided by the total number of pages in the file.

Pages of auto-vacuum overhead

    The number of pages that store data used by the database to facilitate
    auto-vacuum. This is zero for databases that do not support auto-vacuum.

Number of tables in the database

    The number of tables in the database, including the SQLITE_SCHEMA table
    used to store schema information.

Number of indices

    The total number of indices in the database.

Number of defined indices

    The number of indices created using an explicit CREATE INDEX statement.

Number of implied indices

    The number of indices used to implement PRIMARY KEY or UNIQUE constraints
    on tables.

Size of the file in bytes

    The total amount of disk space used by the entire database files.

Bytes of user payload stored

    The total number of bytes of user payload stored in the database. The
    schema information in the SQLITE_SCHEMA table is not counted when
    computing this number.  The percentage at the right shows the payload
    divided by the total file size.

Percentage of total database

    The amount of the complete database file that is devoted to storing
    information described by this category.

Number of entries

    The total number of B-Tree key/value pairs stored under this category.

Bytes of storage consumed

    The total amount of disk space required to store all B-Tree entries
    under this category.  The is the total number of pages used times
    the pages size.

Bytes of payload

    The amount of payload stored under this category.  Payload is the data
    part of table entries and the key part of index entries.  The percentage
    at the right is the bytes of payload divided by the bytes of storage 
    consumed.

Bytes of metadata

    The amount of formatting and structural information stored in the
    table or index.  Metadata includes the btree page header, the cell pointer
    array, the size field for each cell, the left child pointer or non-leaf
    cells, the overflow pointers for overflow cells, and the rowid value for
    rowid table cells.  In other words, metadata is everything that is neither
    unused space nor content.  The record header in the payload is counted as
    content, not metadata.

Average payload per entry

    The average amount of payload on each entry.  This is just the bytes of
    payload divided by the number of entries.

Average unused bytes per entry

    The average amount of free space remaining on all pages under this
    category on a per-entry basis.  This is the number of unused bytes on
    all pages divided by the number of entries.

Non-sequential pages

    The number of pages in the table or index that are out of sequence.
    Many filesystems are optimized for sequential file access so a small
    number of non-sequential pages might result in faster queries,
    especially for larger database files that do not fit in the disk cache.
    Note that after running VACUUM, the root page of each table or index is
    at the beginning of the database file and all other pages are in a
    separate part of the database file, resulting in a single non-
    sequential page.

Maximum payload per entry

    The largest payload size of any entry.

Entries that use overflow

    The number of entries that user one or more overflow pages.

Total pages used

    This is the number of pages used to hold all information in the current
    category.  This is the sum of index, primary, and overflow pages.

Index pages used

    This is the number of pages in a table B-tree that hold only key (rowid)
    information and no data.

Primary pages used

    This is the number of B-tree pages that hold both key and data.

Overflow pages used

    The total number of overflow pages used for this category.

Unused bytes on index pages

    The total number of bytes of unused space on all index pages.  The
    percentage at the right is the number of unused bytes divided by the
    total number of bytes on index pages.

Unused bytes on primary pages

    The total number of bytes of unused space on all primary pages.  The
    percentage at the right is the number of unused bytes divided by the
    total number of bytes on primary pages.

Unused bytes on overflow pages

    The total number of bytes of unused space on all overflow pages.  The
    percentage at the right is the number of unused bytes divided by the
    total number of bytes on overflow pages.

Unused bytes on all pages

    The total number of bytes of unused space on all primary and overflow 
    pages.  The percentage at the right is the number of unused bytes 
    divided by the total number of bytes.
}

# Output a dump of the in-memory database. This can be used for more
# complex offline analysis.
#
titleline {}
puts "The entire text of this report can be sourced into any SQL database"
puts "engine for further analysis.  All of the text above is an SQL comment."
puts "The data used to generate this report follows:"
puts "*/"
puts "BEGIN;"
puts $tabledef
unset -nocomplain x
mem eval {SELECT * FROM space_used} x {
  puts -nonewline "INSERT INTO space_used VALUES"
  set sep (
  foreach col $x(*) {
    set v $x($col)
    if {$v=="" || ![string is double $v]} {set v '[quote $v]'}
    puts -nonewline $sep$v
    set sep ,
  }
  puts ");"
}
puts "COMMIT;"

} err]} {
  puts "ERROR: $err"
  puts $errorInfo
  exit 1
}
