<?php

$site_categ = $_GET['categ'];
/* TODO: log file permission issue */
$cmd = "python3 fc_update.py -c $site_categ >/tmp/fc_update.php.log 2>&1";
$res = exec($cmd, $output, $ret);

if ($ret == 0) {
	echo "success";
} else {
	header('HTTP/1.1 500 Internal Server Error');
}

exit();

?>