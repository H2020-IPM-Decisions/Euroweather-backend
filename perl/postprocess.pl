#!/usr/bin/perl 

use strict;
use File::Basename;
my $dirname = dirname(__FILE__);
#
my $split="$dirname/split.pl";
my $cdmfile="$dirname/cdmGribReaderConfig.xml";
my $commonDigits=shift @ARGV;
my $outfile=shift @ARGV;
my $list="";
foreach my $file (@ARGV) {
    #if ($file =~ m/^(.*\/)([^\/]*TOT_PREC)\.(grib.*)$/) {
    if ($file =~ m/^(.*\/)([^\/]*)\.(grib.*)$/) {
	my $cmd="$split -k 1 -o $1 $file";
	my $retval=system($cmd);
	if ($retval==0) {
	    my $newfile="${1}${2}_1.${3}";
	    $list=$list . " " . $newfile;
	} else {
	    print("Unable to execute: $cmd\n");
	    $list=$list . " " . $file;
	}
    } else {
	print("Not a precipitation file: $file \n");
	$list=$list . " " . $file;
    }
}
if ($list) {
    my $cmd;
    if ($outfile =~ m/^(.*)\.nc.*$/) {
	my $gribfile= $1 . $commonDigits . ".grib";
	$cmd="cat $list > $gribfile;";
	$cmd=$cmd . "fimex-1.6 --input.file $gribfile --input.config $cdmfile --output.file ${1}${commonDigits}.nc;";# ln -sf ${1}${commonDigits}.nc $outfile";
    } elsif ($outfile =~ m/^(.*)\.grib.*$/) {
	$cmd="cat $list > $outfile;";
    };
    my $retval=system($cmd);
    if ($retval==0) { # exit=0 in Unix means ok
	print "$cmd ...OK\n";
    }else {
	print "$cmd ...FAILED\n";
    }
}
