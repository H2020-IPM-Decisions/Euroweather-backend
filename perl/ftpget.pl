#!/usr/bin/perl 

use strict;
use File::Basename;
use File::Copy;
use Net::FTP;
use Date::Parse;
use List::Util qw[min max];
use File::stat;

sub Usage {
    print STDERR "
Usage: ftpget.pl [options] [<path/mask>]...

Download files matching <path/mask> (ftp glob) from ftp-server.

The script uses a lockfile to prevent multiple instances running at same time.
The script uses a register file to store a list of the files on the server.
The script will not download new files (that are being created on the server).
The script determines which files are interesting based on their age relative to the newest file.
Only interesting files are sent to the post-processing script.
The Mail-option for system errors has not been tested properly.

Note that you have to specify which time-zone the server is operating in (i.e. \"GMT\", \"+0200\").

Valid options:

  -l <file> name of lockfile (makes sure only one process of script is running)
           default is \$HOME/.lockfile

  -r <file> name of registerfile (keeps track of downloaded files).
           default is \$HOME/.register

  -w <dir> name of work directory (where temporary files are put).
           default is /tmp

  -o <dir> name of output directory (where final files are put).
           default is ./

  -c <mask> clean temp and output directory using mask (glob).

  -d       dry run, no download!!!

  -v       verbose, print output

  -t <delay\@zone> delay before loading new files (hours) and the server time zone.

  -a <age> maximum allowed age difference to latest file (hours) to be interesting.

  -b <mask> directory bins.

  -n <age> minimum age of newest file in directory bin (hours) for directory to be interesting.

  -s <user\@server:password> user, name of server and password.

  -x <script\@options> name of post-processing script to execute on new and interesting files.
              Command is: <script> <options> file1 file2 file3 ... filen
  
  -f Run script anyways.

  -m <owner> email adress to owner (system error notifications).

\n";
    exit 1;
}

my $home = $ENV{HOME};

my $lockfile       = "$home/.lockfile";  # process lock file to avvoid duplicate processing
my $regfile        = "$home/.register";  # register file keeps track of downloaded files

my $ftp;
my $ftp_host       = 'Xopendata.dwd.de';
my $ftp_user       = "Xanonymous";
my $ftp_passwd     = "Xfranktt\@met.no";

my $ftp_file_done = "done";

my $sleep = 0;

my $workDir = "/tmp";
my $destDir = "";

my @clean=();
my $dry = 0;
my $verbose = 0;

my $force;
my $script="";

my $tz="GMT"; # GMT, MEST, MET, +0200, -0600
my $td=0;
my $maxdiff;
my $minbinage=0.15;
my $binmask;

my @owners = ();
my %Mail = ();

# interpret input

while ($_ = $ARGV[0],/^-./) {
    shift;
    my $pattern = $_;
    if ($pattern =~ /^-l$/) {$lockfile = shift @ARGV; next;}
    if ($pattern =~ /^-r$/) {$regfile = shift @ARGV; next;}
    if ($pattern =~ /^-w$/) {$workDir = shift @ARGV; next;}
    if ($pattern =~ /^-o$/) {$destDir = shift @ARGV; next;}
    if ($pattern =~ /^-c$/) {push (@clean,shift @ARGV); next;}
    if ($pattern =~ /^-d$/) {$dry=1; next;}
    if ($pattern =~ /^-v$/) {$verbose=1; next;}
    if ($pattern =~ /^-a$/) {$maxdiff = shift @ARGV; next;}
    if ($pattern =~ /^-n$/) {$minbinage = shift @ARGV; next;}
    if ($pattern =~ /^-b$/) {$binmask = shift @ARGV; next;}
    if ($pattern =~ /^-s$/) {
	my $arg=shift @ARGV;
	if ($arg =~ m/^([^@]*)@([^:]*):(.*)$/) {
	    $ftp_host=$2;
	    $ftp_user=$1;
	    $ftp_passwd=$3;
	    print(">>>> Host= $ftp_host (User= $ftp_user)\n");
	} else {
	    print(">>>> Unable to interpret \"$arg\"\n");
	};next;}
    if ($pattern =~ /^-t$/) {
	if (shift =~ m/^([^@]*)@([^@]*)$/) {
	    $ftp_host=$2;
	    $ftp_user=$1;
	    $ftp_passwd=$3;
	};next;}
    if ($pattern =~ /^-m$/) {push(@owners,shift @ARGV); next;}
    if ($pattern =~ /^-f$/) {$force = 1; next;}
    if ($pattern =~ /^-x$/) {$script = shift @ARGV; next;}
    &Usage;
}

# get directories and masks from arguments...
my @dirs=();
my @masks=();

####push (@ARGV,"/weather/nwp/cosmo-d2/grib/21/cosmo-d2_germany_regular-lat-lon_single-level_*.grib2.bz2");

foreach my $arg (@ARGV) {
    if ($arg =~ m/^(.*)\/([^\/]*)$/) {
	push (@dirs,$1);
	push (@masks,$2);
    };
};


# make paths absolute...
chomp(my $jobDir = `pwd`);
if ( $destDir && $destDir !~ m/^\// ) { 
    $destDir = $jobDir."/".$destDir;
}
if ( $workDir !~ m/^\// ) { 
    $workDir = $jobDir."/".$workDir;
}
if ( $regfile !~ m/^\// ) { 
    $regfile = $jobDir."/".$regfile;
}
if ( $lockfile !~ m/^\// ) { 
    $lockfile = $jobDir."/".$lockfile;
}
if ( $script && $script !~ m/^\// ) { 
    $script = $jobDir."/".$script;
}

# Make sure directories have trailing '/'
if ( $destDir && $destDir !~ m/\/$/ ) { $destDir=$destDir . '/';} 
if ( $workDir !~ m/\/$/ ) { $workDir=$workDir . '/';} 

# Make sure output directories exist (mkdir -P makes parents)

if (!mkdir($workDir)) {print ">>>> Unable to make $workDir\n";}
if ($destDir && !mkdir($destDir)) {print ">>>> Unable to make $destDir\n";}

if (-e $lockfile) { # something is fishy...
    # this changes ctime and mtime, but not atime...
    open(MLOCKFILE, ">$lockfile") 
	or die("Couldn't open Lockfile: '$lockfile'.\n");
    die "$lockfile already locked\n" unless (flock (MLOCKFILE,2+4));
    # ...hmm, lockfile is not flocked. Location could be virtual...
    # Remove lockfile if it is old.
    my $sb= stat($lockfile);
    my $age=(time() - $sb->atime)/3600; # hours
    #print("Lock file age: $age ($lockfile) ".(time())."\n");
    #die"Hard";
    if ($age > 0.10) {unlink($lockfile);print ">>>> Old $lockfile removed (".sprintf("%.2f",$age)."h).\n"; }; # abort if lockfile is newer than 0.25 hours...
    if (-e $lockfile) {die "$lockfile is too new to ignore (".sprintf("%.2f",$age)."h)."};
};
# lockfile should not exist at this point...
open(MLOCKFILE, ">$lockfile") 
    or die("Couldn't open Lockfile: '$lockfile'.\n");
die "$lockfile already locked\n" unless (flock (MLOCKFILE,2+4));

    
# Initialise local variables

my $myname = basename($0);
my $user = qx(/usr/bin/whoami); chomp($user);
my $host = qx(/bin/uname -n); chomp($host);
my $homeDir  = $ENV{HOME} || "/home/$user";

my $ret=0;
my $retval=1;
my $delay=0; # delay processing as files are being uploaded...

#### load old register (hash reference, dereference using: %$local_files
my $processedafile=0;
my $local_files = getRegister($regfile);
if (! %$local_files) {$processedafile=1;}
my $remote_files = {};
my $remote_dir = {};
my $remote_age = {};

####require "stat.pl" ;

my $EVAL_ERROR;

# Download data

chdir($workDir) or rip("Unable to chdir $workDir");

#    # download new files using ftp
print ">>>> Connecting to $ftp_host\n";

# Open FTP connection and authenticate
#### timeout applies to dir-command...
#### mode needs to be passive or "DIR" will not work...

$ftp = Net::FTP->new($ftp_host, Debug => $verbose,  Timeout => 3, Passive => 1)
    or rip("Couldn't connect to $ftp_host ($@)");
if ($sleep) {sleep $sleep;}
$ftp->login($ftp_user, $ftp_passwd)
    or rip("Couldn't login to $ftp_user at $ftp_host ($@)");
if ($sleep) {sleep $sleep;}
$ftp->binary();

# list of files retrieved from remote server    
my @retrieved_files=();

# latest files (used as reference for throwing "old" files)...
my $minage;
my $minpath;

# loop over directories and patterns on remote server, find latest file
my $ftp_cdir="";
my $cnt=0;

my %orm;
my %ook;

# get directory bins
my %binages;
my %binfiles;
if ($binmask =~ m/^(.*)\/([^\/]*)$/) {
    my $bin_directory=$1;
    my $bin_mask=$2;
    $ftp->cwd($bin_directory) or 
	rip("Cwd operation to '$bin_directory' failed ($@)");
    $ftp_cdir=$bin_directory;
    my @remote_list = $ftp->dir($bin_mask);
    print(">>>> Found ".(scalar(@remote_list))." files in $bin_directory ($bin_mask)\n");
    foreach my $line (@remote_list) {
	my $age=240.0;
	if ($line =~ m/^(.*\s+)(\S+)$/) {
	    my $path=$bin_directory . "/" . $2;
	    $binages{$path} = $age; # a long time ago...
	    $binfiles{$path} = []; # files in this bin..
	}
    };
};
my $nloc=scalar(@dirs);
for (my $ii=0; $ii<$nloc;$ii++) {
    my $ftp_directory=shift @dirs;
    my $ftp_mask=shift @masks;
    if ($sleep) {sleep $sleep;}
    if (! $ftp_cdir || $ftp_cdir ne $ftp_directory) {
	$ftp->cwd($ftp_directory) or 
	    rip("Cwd operation to '$ftp_directory' failed ($@)");
	$ftp_cdir=$ftp_directory;
    }
    #    if ($sleep) {sleep $sleep;}
    # find bin dir...
    my $bindir;
    for my $key (keys %binages) {
	if ($ftp_directory =~ m/^\Q$key\E/) {
	    $bindir=$key;
	};
    };
    my @remote_list = $ftp->dir($ftp_mask);
    my $lcnt=0;
    foreach my $line (@remote_list) {
	if ($verbose) {print ">>>> $line\n";}
	if ($line =~ m/^(.*\s+)(\S+)$/) {
	    my $path=$ftp_directory . "/" . $2;
	    $cnt=$cnt+1;
	    $lcnt=$lcnt+1;
	    my $age=getAge($line);
	    if ($bindir) {
		$binages{$bindir}=min($age,$binages{$bindir});
		push(@{$binfiles{$bindir}},$path);
	    };	    
	    if ($age<$td) { # file is being uploaded...
		$delay=1;
		if ($verbose) {print ">>>> Too new: $path (Age=".sprintf("%.1f",$age)." < $td)\n";}
		$orm{"Files on server"}=($orm{"Files on server"}||0)+1;
	    } else {
		$ook{"Files on server"}=($ook{"Files on server"}||0)+1;
		$remote_files->{$path} = $1 . $path;
		$remote_dir->{$path} = $ftp_directory;
		$remote_age->{$path} = $age;
		if (!$minage || $age < $minage) {
		    $minage=$age;
		    $minpath=$path;
		}
	    }
	}
    };
    print ">>>> Found $lcnt files in $ftp_directory ($ftp_mask)";
    if ($bindir) {print " => ".sprintf("%.1f",$binages{$bindir})."hrs";};
    print "\n";
}
print ">>>> Found $cnt files on $ftp_host\n";
# print ages:
my $maxage;
my $maxkey;
my $minage;
my $minkey;
if ($binmask) {
    for my $key (keys %binages) {
	my $age=sprintf("%.1f",$binages{$key});
	if ($age > $minbinage && (! defined($minage) || $age < $minage)) { 
	    $minage=$age;
	    $minkey=$key;
	};
	if ($age > $minbinage && (! defined($maxage) || $age > $maxage)) { 
	    $maxage=$age;
	    $maxkey=$key;
	};
    };
    print ">>>> Bin directory:  ${minkey} => ${minage}hrs [${maxkey} => ${maxage}hrs]\n";
} else {
    print ">>>> No bin directory available.\n";
}
if ($dry) {print ">>>> This is a DRY RUN!\n";};
# retrieve external files not present in local register
$cnt=0;
my @selected_files;
if ($minkey) {
    @selected_files=@{$binfiles{$minkey}};
    $orm{"Selected bin"}=scalar(keys %$remote_files)-scalar(@selected_files);
} else {
    @selected_files=sort keys %$remote_files
};
my $commonDigits=&findCommonDigits(@selected_files);
print ">>>>> Common digits: $commonDigits\n";
foreach my $path (@selected_files) {
    $ook{"Selected bin"}=($ook{"Selected bin"}||0)+1;
    my $ftp_directory=$remote_dir->{$path};
    my $age=$remote_age->{$path};
    if ($maxdiff && $age-$minage > $maxdiff) {
	if ($verbose) {print ">>>> Old file   $path (".sprintf("%.1f",$age)."-".sprintf("%.1f",$minage).">$maxdiff)\n";}
	$orm{"Not too old"}=($orm{"Not too old"}||0)+1;
    } else {
	$ook{"Not too old"}=($ook{"Not too old"}||0)+1;
	my $line=$remote_files->{$path};
	if (exists($local_files->{$path}) and $local_files->{$path} eq $remote_files->{$path}) {
	    if ($verbose) {print ">>>> File not changed: $path\n";}
	    $orm{"Not in register"}=($orm{"Not in register"}||0)+1;
	    (my $file) = ($path =~ m/^.*\/(\S+)$/);
	    if ($file =~ m/^(.*).gz$/) {
		$file=$1;
	    }
	    if ($file =~ m/^(.*).bz2$/) {
		$file=$1;
	    }
	    if ($destDir) {
		my $target=$destDir . $file;
		push(@retrieved_files, $target);
	    } else {
		push(@retrieved_files, $file);
	    }
	} else {
	    $ook{"Not in register"}=($ook{"Not in register"}||0)+1;
	    (my $file) = ($path =~ m/^.*\/(\S+)$/);
	    $processedafile=1;
	    if ($sleep) {sleep $sleep;}
	    if (! $dry) {
		$ook{"dry"}=($ook{"dry"}||0)+1;
		if ($verbose) {print ">>>> Processing $path (Age=".sprintf("%.1f",$age)."h)\n";}
		if (! $ftp_cdir || $ftp_cdir ne $ftp_directory) {
		    $ftp->cwd($ftp_directory) or 
			rip("Cwd operation to '$ftp_directory' failed ($@)");
		    $ftp_cdir=$ftp_directory;
		}
		if ($ftp->get($file)) {
		    print ">>>> Downloaded $file ($ftp_directory)\n";
		    $ook{"Downloaded"}=($ook{"Downloaded"}||0)+1;
		    if ($file =~ m/^(.*).gz$/) {
			$retval=system "gunzip -f $file";
			if ($retval==0) { # success
			    $file=$1;
			    if ($verbose) {print ">>>> gunzip $file\n";}
			} else {
			    print ">>>> failed gunzip -f $file\n";
			}
		    }
		    if ($file =~ m/^(.*).bz2$/) {
			$retval=system "bunzip2 -f $file";
			if ($retval==0) { # success
			    $file=$1;
			    if ($verbose) {print ">>>> bunzip $file\n";}
			} else {
			    print ">>>> failed bunzip2 $file\n";
			}
		    }
		    # move file to dest dir
		    $cnt=$cnt+1;
		    if ($destDir) {
			my $target=$destDir . $file;
			move($file, $target) or print(">>>> Move failed: $target\n");
			push(@retrieved_files, $target);
		    } else {
			push(@retrieved_files, $file);
		    }
		} else {
		    if ($verbose) {print STDERR ">>>> Couldn't retrieve file $file ($@)";}
		    $orm{"Downloaded"}=($orm{"Downloaded"}||0)+1;
		}
	    } else {
		$orm{"dry"}=($orm{"dry"}||0)+1;
		if ($verbose) {print ">>>> Found file   $path (".sprintf("%.1f",$age)."-".sprintf("%.1f",$minage).">$maxdiff)\n";}
		if ($file =~ m/^(.*).gz$/) {
		    $file=$1;
		}
		if ($file =~ m/^(.*).bz2$/) {
		    $file=$1;
		}
		# move file to dest dir
		$cnt=$cnt+1;
		if ($destDir) {
		    my $target=$destDir . $file;
		    move($file, $target) or print(">>>> Move failed: $target\n");
		    push(@retrieved_files, $target);
		} else {
		    push(@retrieved_files, $file);
		}
	    }
	}
    }
}
# Close ftp-connection (not really necessary...)

print ">>>> Found $cnt new and interesting files on $ftp_host.\n";
if ($sleep) {sleep $sleep;}
$ftp->quit() or print ">>>> Cannot close FTP connection.  Oh well.\n";

# update register
if ($processedafile) {
    setRegister($regfile,$remote_files);
};

&printSummary("Files on server");
&printSummary("Selected bin");
&printSummary("Not too old");
&printSummary("Not in register");
&printSummary("Downloaded");

if ($script && ($force || $processedafile)) {
    if ($delay) {
	print ">>>> Files are being uploaded. Omitting post-processing script.\n";
    } else {
	print(">>>> Post-Processing ".scalar(@retrieved_files)." files...\n");
	postProcess($script,$commonDigits,@retrieved_files);
    }
} elsif (!$script && $processedafile) {
    print ">>>> No post-processing script was specified.\n";
} elsif ($script && !$processedafile) {
    print ">>>> The post-processing script is only executed if new and interesting files are found.\n";
} else {
    print ">>>> No files were post-processed.\n";
}

if (@clean) {
    foreach my $cc (@clean) {
	if ($workDir) {clean($workDir,$cc,"+2");}
	if ($destDir) {clean($destDir,$cc,"+2");}
    }
};

#use Data::Dumper;
#print Dumper(%ook);
#print Dumper(%orm);

# Unlock lock-file...
close LOCKFILE;
unlink($lockfile) || print(">>>> Unable to remove $lockfile\n");

########################################################################
#                                                                      #
########################################################################

sub printSummary {
    my $key=shift;
    my $xok=$ook{$key}||0;
    print ">>>> $key: $xok ok";
    my $xrm=$orm{$key}||"";
    if ($xrm) { print " ($xrm removed)";};
    print "\n";
};
sub postProcess{
    my $script=shift;
    my $commonDigits=shift;
    my @retrieved_files=@_;
    my $options="";
    if ($script =~ m/^([^@]*)@([^@]*)$/) {
	$script=$1;
	$options=$2;
    };
    my @args=($commonDigits);
    foreach my $arg (split / /,$options) {
	push (@args,$arg);
    }
    foreach my $arg (sort @retrieved_files) {
	push (@args,$arg);
    }
    #foreach my $arg (@args) {
	#print("Argument ($script): $arg\n");
    #}
    print("Executing $script with ".(scalar(@args))." arguments.\n");
    if (-x $script) {
	my $retval=system($script,@args);
	if ($retval==0) {
	    print ">>>> Executed $script successfully.\n";
	} else {
	    print ">>>> Failed executing $script ($options)\n";
	};
    } else {
	if ($verbose) {print ">>>> Unable to find the script \"$script\"\n";}
    }
}

sub getRegister {
    my $registerfile=shift;
    my %local_files;
    # Load register from local register file 
    if ($verbose) {print ">>>> Reading register file: $registerfile\n";}
    if (not open(REGISTER, "<$registerfile")) { 
	my $subject = "$myname: Unable to open $registerfile";
	my $reason = '';
	Email($reason,$subject, @owners);
	#	 SendEmail();
	#	 die "$subject";
    }
    while (<REGISTER>) {
	chomp;
	my $line=$_;
	(my $path) = ($line =~ m/^.*?\s+(\S+)$/);
	# $d =~ s/\s+/ /g;
	if ($verbose > 1) {print(">>>> Old register $path\n");};
	$local_files{$path} = $line;
    }
    close REGISTER;
    return \%local_files;
}

sub setRegister {
    my $registerfile=shift;
    my $remote_files=shift;
    if ($verbose) {print ">>>> Writing register file: $registerfile\n";}
    if (not open (REGISTER,">$registerfile")) {
	my $subject = "$myname: Unable to open $registerfile";
	my $reason = '';
	Email($reason,$subject, @owners);
	#	 SendEmail();
	#	 die "$subject\n";
    }
    foreach my $path (keys %$remote_files) {
	if ($verbose > 1) {print(">>>> New register $path\n");}
	print REGISTER $remote_files->{$path} . "\n";
    }
    close REGISTER;
};

sub Email {
    my ($reason,$subject, @owners) = @_;
    for my $owner ( @owners ) {
	$Mail{$owner} .= "$subject\n";
	$Mail{$owner} .= "  Reason=$reason\n" if ($reason);
    }
}

sub SendEmail {
    for my $owner ( keys %Mail ) {
	if ($verbose) {print ">>>> Sending e-mail to  $owner\n";}
	open(MH,"|/usr/bin/Mail -s \'Warnings from $user running $myname at $host\' $owner") || die "Could not mail\n";
	print MH $Mail{$owner};
	close(MH);
    }
}

########################################################################
#                                                                      #
########################################################################

sub getAge {
    my $line=shift;
    if ($line =~ m/.*\s(\S+\s\d+\s\d+:\d+)\s(\S*)$/) {
	my $epoch=str2time($1,$tz);
	my $now=time();
	my $age=($now-$epoch)/3600;
	#print "$1 -> $epoch ($tz) $age\n";
	return $age;
    };
}

sub overlap {
    my $str1=shift;
    my $str2=shift;
    my $len1=length($str1);
    my $len2=length($str2);
    my $lenmin=min($len1,$len2);
    my $lenmax=max($len1,$len2);
    my $noteq=$lenmax-$lenmin; 
    for (my $ii=0;$ii<$lenmin;$ii++) {
	if (substr($str1,$ii,1) ne substr($str2,$ii,1)) {
	    $noteq=$noteq+1;
	}
    }
    return $noteq;
}


sub clean {
    my ($dir, $mask, $time) =@_;
    if (-d $dir) {
	my $cmd="find $dir -name \"$mask\" -mtime $time -print 2> /dev/null";
	if ($verbose) {print ">>>> Cleaning using \"$cmd\"\n"; }
	my @tmp = qx($cmd);
	for (@tmp) 
	{ 
	    if ($verbose) {print ">>>> Removing $_\n"; }
	    chomp; 
	    unlink; 
	}
    } else {
	if ($verbose) {print ">>>> Unable to clean $dir\n";}
    }
}

sub rip {
    my $msg=shift;
    unlink($lockfile) || print(">>>> Unable to remove $lockfile\n");
    die($msg);
}

sub findCommonDigits {
    my @files=@_;
    my @basenames=();
    foreach my $file (@files) {
	if ($file =~ m/([^\/]+)$/) {
	    push (@basenames,$1);
	}
    };
    my $model= pop @basenames;
    my $len= length($model);
    print ("Model $model, $len\n");
    for my $item ( @basenames  ) {
        my $dif= $model ^ substr($item,0,$len);
        $len= length( ( $dif =~ /^(\0+)/ )[0] || '');
        substr( $model, $len )= "";
	print ("Comparing $item ($model), $len\n");
    };
    # get longest common string of digits in prefix...
    my $res="";
    while ($model =~ /([\d]+)/g) {
	if (length($1) > length($res)) {
	    $res=$1;
	};
    };
    return $res;
}


#==============================================
#  End task.
#==============================================

