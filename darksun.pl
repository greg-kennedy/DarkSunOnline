#!/usr/bin/env perl

use strict;
use warnings;

use IO::Socket::INET;
# auto-flush on socket
$| = 1;


# Creating a listening socket
my $socket = new IO::Socket::INET (
    LocalHost => '0.0.0.0',
    LocalPort => '14902',
    Proto => 'tcp',
    Listen => 5,
    Reuse => 1
);
die "Cannot create socket $!\n" unless $socket;

# $SIG{INT} = sub { $socket->close(); exit 0; };

while(1) {
    my $client_socket = $socket->accept();

    # Get information about a newly connected client
    my $client_address = $client_socket->peerhost();

	while (1) {
		# Read 2 bytes of packet len
		my $buf = "";
		$client_socket->recv($buf, 1);
		last if ($buf eq ""); # client disconnect
		my $len = ord($buf) - 2;

		$client_socket->recv($buf, 1);
		my $pkt_flags = ord($buf);
		
		my $extra_flags;
		if ($pkt_flags) {
			# extra bits follow
			$client_socket->recv($buf, 1);
			$extra_flags = ord($buf);
			$len --;
		} else {
			$extra_flags = 0;
		}

		# read DS and TYPE
		$client_socket->recv($buf, 4);
		my ($ds, $type) = unpack('A2A2', $buf);
		$len -= 4;
		
		# read remaining len bytes
		$client_socket->recv($buf, $len);

		# and turn the buf into a formatted hexdump
		my $payload = '';
		foreach my $c (unpack 'C*', $buf) {
			$payload .= sprintf('0x%02x [%c] ', $c, 
			  ($c >= 0x20 && $c < 0x7F ? $c : 0x20));
		}
		print("$client_address: Received packet\n\tlen=$len\n\tpkt_flags=$pkt_flags\n\textra_flags=$extra_flags\n\tds=$ds\n\ttype=$type\n\tpayload=$payload\n\n");

		# respond
		if ($type eq 'IT') {
			# this is a TEN Init which contains the Token.
			#  should check this against the user DB.
			# send response
#			my $buf = pack('vA2A2vva*', 11, 'ds', 'IN', 1, 0, "\0");
			my @resp = (
			0x37, 0x80,
			0x4, 0x64, 0x73, 0x49, 0x4e,
			0x1, 0xfe,
			0x4, 0x1, 0x1, 0x1, 0x1,
			0xa, 0xfe, 0xa, 0x35, 0x37, 0x30, 0x38, 0x38, 0x30, 0x31,    0x36, 0x34, 0x0,
	0x1, 0xfe, 0x0,
	0xa, 0xfe,
    0x8, 0x35, 0x37, 0x30, 0x38, 0x38, 0x30, 0x31, 0x36, 0x34, 0xfc,
	0x0, 0x1, 0xf9,
	0x0, 0x1, 0xf9,
	0x0, 0x1, 0xfd,
	0x0, 0x1, 0xfe);
			my $buf = pack('C*', @resp);
			print("$client_address: Sending packet " . length($buf) . "\n");
			my $sent = $client_socket->send($buf);
			print("\tsent $sent\n");
		} elsif ($type eq 'LG') {
			# client log - already printed so dw about it
		}
	}
}