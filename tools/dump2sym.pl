#!/usr/bin/env perl
use strict;
use warnings;
use autodie;

my $section = 0;
open my $fp, '<', $ARGV[0];
while (my $line = <$fp>) {
  chomp $line;
  if ($line =~ m/Global Info/) {
    my $discard = <$fp>;
    my $section = 1;
    while ($section) {
      my $name = <$fp>;
      if ($name =~ m/^\s*$/) {
        last;
      }
      my $address = <$fp>;
      my $module_index = <$fp>; 
      my $kind = <$fp>;

      if ($name =~ m/Name:\s+(\S+)/) {
        print "$1 ";
      }
      if ($address =~ m/:([0-9A-F]+)/) {
        print "$1 ";
      }
      if ($kind =~ m/\(data\)/) {
        print "l";
      } else {
        print "f";
      }
      print "\n";
    }
    last;
  }
}
