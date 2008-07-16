<?php
  //
  // This webpage lists users, their datastore snapshots and the
  // documents within them. If a document is requested, it will
  // pack in on the fly as a 'Journal Entry Bundle' as described
  // here: http://wiki.laptop.org/go/Journal_entry_bundles
  //
  // Notes:
  //  - This is a _temporary_ restoration tool, as it does
  //    not enforce authentication or access control.
  //
  //  - In case you are wondering about the choice of prog
  //    language, the intention is to integrate this into
  //    Moodle as soon as authentication is sorted :-)
  //
  // Author: Martin Langhoff <martin@laptop.org>
  // Copyright: One Laptop per Child Foundation
  // License: GPLv3
  //
  //
  //
  // pre-output processing
  //

  //phpinfo();exit;

$baseurl = 'http://' . $_SERVER['HTTP_HOST']
    . $_SERVER['SCRIPT_NAME'];
$params = array();
if (isset($_SERVER['PATH_INFO'])) {
  $params = explode('/', $_SERVER['PATH_INFO']);
  array_shift($params); // leading slash means first one is always empty
}

$homedirbase = '/library/users';

/**
 * Die with an error consistently in cli and web-serving cases.
 *
 * - Print an error to STDERR and exit with a non-zero code.
 * - Set an error code of 500 and log the error.
 *
 * Default errorcode (only used in cli) is 1.
 *
 * Very useful for perl-like error-handling:
 *
 * do_somethting() or mdie("Something went wrong");
 *
 * @param string  $msg       Error message
 * @param integer $errorcode Error code to emit
 */
function mdie($msg='', $errorcode=1) {
  if (isset($_SERVER['GATEWAY_INTERFACE'])) {
        header($_SERVER['SERVER_PROTOCOL'] . ' 500 Server Error');
        error_log($msg);
	exit();
    } else {
        error_log($msg);
	exit($errorcode);
    }
}

/*
 * make_journal_entry_bundle()
 *
 * Will read a ds entry from the given
 * ds path, and return a filepath to a
 * properly formed JEB tempfile.
 *
 * The caller is responsible for
 * the tempfile (caching, removal, etc).
 *
 */
function make_journal_entry_bundle($dspath, $uid) {

  // We use /var/tmp as we will store larger
  // files than what /tmp may be prepared to
  // hold (/tmp may be a ramdisk)
  $filepath = tempnam('/var/tmp', 'ds-restore-');

  $zip = new ZipArchive();

  if ($zip->open($filepath, ZIPARCHIVE::OVERWRITE)!==TRUE) {
    mdie("cannot open <$filepath>\n");
  }
  // Main file
  $zip->addFile("$dspath/$uid", "$uid/$uid")
    || mdie("Error adding file $dspath/$uid");
  $zip->addFile("$dspath/$uid.metadata", "$uid/_metadata.json")
    || mdie("Error adding metadata");
  if (file_exists("$dspath/preview/$uid")) {
    $zip->addFile("$dspath/preview/$uid", "$uid/preview/$uid")
      || mdie("Error adding preview");
  }
  $zip->close()
    || mdie("Error zipping");
  return $filepath;
}

function print_userhomes($userhomes) {
  global $homedirbase, $baseurl;

  echo '<h1>User listing</h1>';
  echo '<ul>';
  while ($direntry = readdir($userhomes)) {
    if ($direntry === '.' || $direntry === '..') {
      continue;
    }
    $dspath = $homedirbase . '/' . $direntry . '/datastore-latest';

    if (is_dir($dspath)) {
      // $bn needs Moodle's s()/p() style scaping
      $bn = basename($direntry);
      echo "<li><a href=\"{$baseurl}/{$direntry}/datastore-latest\">"
	. "$bn</a></li>\n";
    }

  }
  echo '</ul>';
}

function print_dsdir($dsbasepath, $dsdir) {
  global $homedirbase, $baseurl;

  $dspath = $dsbasepath.'/store';

  echo '<h1>Data Store listing</h1>';
  echo '<ul>';

  $latest = false;
  if (is_link($dsbasepath)) {
    $latest = true;
    $dsbasepath = readlink($dsbasepath);
  }

  // Extract UTC datestamp
  // For Later - regex and mktime() lines to get epoch:
  // '/^datastore-(\d{4})-(\d{2})-(\d{2})_(\d{2}):(\d{2})$/'
  // $epoch = mktime($match[4], $match[5], $match[2], $match[3], $match[1]);
  if (!preg_match('/^datastore-(\d{4}-\d{2}-\d{2}_\d{2}:\d{2})$/',
		  basename($dsbasepath), $match)) {
    mdie("Malformed datastore directory - " . $dsbasepath);
  }
  $timestamp = $match[1];
  echo "<p>Snapshot taken at $timestamp";
  if ($latest) {
    echo "- this is the most recent snapshot taken";
  }
  echo '. <a href="';
  echo $baseurl . dirname($_SERVER['PATH_INFO']);
  echo '">View all snapshots</a></p>';

  while ($direntry = readdir($dsdir)) {
    // we will only look at metadata files,
    // capturing the "root" filename match
    // in the process
    if (!preg_match('/^(.*)\.metadata$/',$direntry, $match)) {
      continue;
    }
    $filename = $match[1];
    $filepath = $dspath . '/' . $filename;
    $mdpath = $dspath . '/' . $direntry;
    if (!is_file($filepath) || !is_file($mdpath)) {
      continue;
    }

    // Read the file lazily. Memory bound.
    // (but the json parser isn't streaming, so...)
    $md = json_decode(file_get_contents($mdpath));

    if (!is_object($md)) {
      continue;
    }
    echo '<li>'
      . "<a href=\"{$baseurl}{$_SERVER['PATH_INFO']}/{$filename}\">"
      . htmlentities($md->title)
      . '</a> [' . htmlentities($md->activity) . '] '
      . '(' . htmlentities($md->mtime) . ')';

    if (!empty($md->buddies)) { // May be ''
      // Forced to array
      $buddies = json_decode($md->buddies, true);
      $buddynames = array();
      foreach ($buddies as $hashid => $values) {
	// TODO: Something nice with the colours
	$name    = $values[0];
	$colours = $values[1];
	$buddynames[] = htmlentities($name);
      }
      echo '<br />With: ' . implode(', ', $buddynames);
    }
    echo "</li>\n";
  }
  echo '</ul>';
}

///
/// "Main"
///
/// Defines globals for use in the Display part
/// - $dspath
/// - $userhomes
/// - $userhome
/// - Or will just serve a JED
///
if (count($params) === 2) {

  // In Moodle - check that $param[0] matches
  // our username or that we have a suitable capability
  if (!preg_match('/^datastore-/',$params[1])) {
    mdie("Only datastore access is allowed" . $params[1]);
  }
  $dsbasepath = $homedirbase.'/'.$params[0].'/'.$params[1];
  $dspath = $dsbasepath . '/store';
  if (is_dir($dspath)) {
    if (!($dsdir = opendir($dspath))) {
      mdie("Cannot open $dspath");
    }
  }
} elseif (count($params) === 3) {
  $uid = array_pop($params);
  $dspath = $homedirbase . '/' . implode('/', $params);
  $dspath .= '/store';
  $jeb = make_journal_entry_bundle($dspath, $uid);
  header("Content-Type: application/vnd.olpc-journal-entry");
  header("Content-Length: " . filesize($jeb));
  $fp = fopen($jeb, 'rb');
  fpassthru($fp);
  exit;
} else {
  // this would be read_userhomes()
  // if it had any internal vars...
  if (!($userhomes = opendir($homedirbase))) {
    mdie("Cannot open $homedirbase");
  }
}

?>
<html>
<head><title>DS Restore</title>
</head>
<body>
<?php

if (isset($dsdir)) {
  print_dsdir($dsbasepath,$dsdir);
} elseif (isset($userhomes)) {
  print_userhomes($userhomes);
}
?>
</body>
</html>