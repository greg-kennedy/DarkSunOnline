#!/usr/bin/env perl
use strict;
use warnings;
use autodie;

use Fcntl qw( SEEK_SET );
#use Fcntl qw( :seek );

use Carp qw( confess );

sub _rd
{
  my ($fh, $count) = @_;

  my $read = read($fh, my $buffer, $count);

  confess "Short read on $fh: expected $count, got $read" unless $read == $count;

  return $buffer;
}

sub d
{
  my ($name, $val) = @_;
  printf("%s = %u (%08x)\n", $name, $val, $val);
}

#####################

if (scalar @ARGV != 2) {
  print "$0: translates an OpenWatcom Win16/32 DPMI program into a 32-bit PE file\n";
  print "Usage: $0 in.exe out.exe\n";
  exit;
}

print "Opening $ARGV[0]...\n";
open my $fpi, '<:raw', $ARGV[0];

# get the EXE length - the 32-bit Watcom block immediately follows
seek $fpi, 0x38, SEEK_SET;
my $exelen = unpack 'V', _rd($fpi, 4);
d('exelen', $exelen);

# skip to the 32-bit code
seek $fpi, $exelen, SEEK_SET;

# unpack the rex_exe struct
my %exe;
( $exe{sig}, $exe{file_size1}, $exe{file_size2}, $exe{reloc_cnt}, $exe{file_header}, $exe{min_data}, $exe{max_data}, $exe{initial_esp}, $exe{checksum}, $exe{initial_eip}, $exe{first_reloc}, $exe{overlay_number}, $exe{one} ) = unpack('vvvvvvvVvVvvv', _rd($fpi, 30));
print "EXE STRUCT:\n";
foreach my $key (keys %exe) { d($key, $exe{$key}); }

# check signature bytes
if ($exe{sig} != 0x514D ) { die "Bad Watcom sig, is OFFSET correct?" }

# determine file header size
my $file_header_size = ($exe{file_header} + (($exe{one} - 1) * 0x10000)) * 16;
d('file_header_size', $file_header_size);

# get exe data - data start and stack start
my $exe_data_location = $exelen + $file_header_size + $exe{initial_eip};
d('exe_data location', $exe_data_location);

seek $fpi, $exe_data_location, SEEK_SET;
my %exedat;
( $exedat{datastart}, $exedat{stackstart} ) = unpack 'VV', _rd($fpi, 8);
print "EXEDAT STRUCT:\n";
foreach my $key (keys %exedat) { d($key, $exedat{$key}); }

# filesize
my $size = $exe{file_size2} * 512;
if ($exe{file_size1} > 0) {
  $size += $exe{file_size1} - 512;
}
d('filesize', $size);

# stack size
sub align16 { return ($_[0] + 0xF) & 0xFFFFFFF0 }
sub align4k { return ($_[0] + 0xFFF) & 0xFFFFF000 }

my $StackSize = align4k( $exe{initial_esp} - align16($exedat{stackstart}) );
if( $StackSize < 0x1000 ) { $StackSize = 0x1000; }
d('stacksize', $StackSize);

my $minmem = $exe{min_data} * 4096;
my $maxmem;
if( $exe{max_data} == 0xFFFF ) {
    $maxmem = 4096;
} else {
    $maxmem = $exe{max_data} * 4096;
}

$minmem = align4k( $minmem + $size + 0x10000 );
$maxmem = align4k( $maxmem + $size + 0x10000 );
if( $minmem > $maxmem ) {
    $maxmem = $minmem;
}

seek($fpi, $exelen + $file_header_size, SEEK_SET);
my $currsize = $size - $file_header_size;
d('start', $exelen + $file_header_size);
d('currsize', $currsize);

my $block = _rd($fpi, $currsize);

close $fpi;

open my $fpo, '>:raw', $ARGV[1];

print $fpo $block;

close $fpo;
