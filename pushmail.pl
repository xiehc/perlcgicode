#!/usr/bin/perl 
#use strict;
use MIME::Base64;
use IO::Socket;
use Encode;

BEGIN {
     $SIG{__DIE__} = $SIG{__WARN__} = \&die_fatal;
     $SIG{ALRM} = \&alrm_fatal;
}

my $log = "/var/log/pushmail.log";
my $date = `/bin/date +%Y.%m.%d-%H:%M:%S`;
chomp($date);
my $allString = "@ARGV";
my $from = $ARGV[0];
my $sub = $ARGV[1];
my $usermail = $ARGV[2];
my $mid = $ARGV[3];
my $addr = "192.168.0.1";
my $port = "4210";
my $dest = sockaddr_in($port, inet_aton($addr));
my $buf = undef;
my $t= "301";
my $mailcont;
my $contmp;
my $size = -s "./Pushmail/$mid";
open (LOG,">>$log") || die "error open file $log $!\n";

if ($size > 2048000){
print LOG "===start.$date\n";
print LOG "NOSEND mail size too big===USERID\:$usermail====STATUS\:NOSEND===SUBJECT\:$sub===SIZE\:$size ===FROM\:$from\n";
print LOG "===end.$date $mid\n";
#`rm -rf ./Pushmail/$mid`;
unlink "./Pushmail/$mid";
exit;
}else{
#open (FILE,"< ./Pushmail/$mid");
#foreach $contmp (<FILE>){

#$contmp =~ s/^charset=/\tcharset=/g;
#$contmp =~ s/^name=/\tname=/g;
#$contmp =~ s/^filename=/\tfilename=/g;
#$contmp =~ s/boundary=/\n\tboundary=/g;
#$mailcont .=$contmp;
#}
$mailcont =`cat ./Pushmail/$mid`;

$from =~ s/^\s+//g;
$from =~ s/\s+$//g;
$sub =~ s/^\s+//g;
$sub =~ s/\s+$//g;


my $from1;
if ($from =~ m/\s+/) {
        my $where1 = rindex($from," ");
        $from1 = substr($from,$where1);
}else{
        $from1 = $from;
}

$from1 =~ s/^\s+//g;
$from1 =~ s/\s+$//g;

#chomp($usermail);
#chomp($from1);
#chomp($mailcont);
#Encode::_utf8_on($mailcont);


my $busermail = encode_base64($usermail);
my $bfrom = encode_base64($from1);
my $bsub = encode_base64($sub);
my $bmailcont = encode_base64($mailcont);
chomp($busermail);
chomp($bfrom);
chomp($bsub);
$bmailcont =~ s/\n//g;
#chomp($bmailcont);
#open (CONT,">>/root/cont");
#print CONT "$bmailcont";
#close(CONT);

my $xml="<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Data>
<user ID=\"$busermail\">
<from>$bfrom</from>
<subject>$bsub</subject>
<content>$bmailcont</content>
</user>
</Data>";

chomp($xml);
my $l = length($xml);
my $out= pack("NNa*",$t,$l,$xml);
my $f = length($out);

my $sock = IO::Socket::INET->new(
        PeerAddr => $addr,
        PeerPort => $port,
        Proto    => 'tcp',
        Timeout  => 10)
or die "===start.$date\nCan't connect: $!\nUSERID\:$usermail====SUBJECT\:$sub====FROM\:$from1===send\:0\n===end.$date $mid\n";

$bytes_sent = $sock->send($out,0);
alarm(8);
$sock->recv($buf,1024,0);
alarm(0);
$buf =~ s/\s+$//g;

if ($buf =~ /\+OK/i){
print LOG "\n";
print LOG "===start.$date\n";
print LOG "USERID\:$usermail=SIZE\:$size===STATUS\:$buf===SUBJECT\:$sub=======FROM\:$from1=======send\:$bytes_sent bytes\n";
#print LOG "$xml\n";
#print LOG "$mailcont\n";
print LOG "===end.$date $mid\n";

close(SOCK);
close(LOG);
unlink "./Pushmail/$mid";
}else{
print LOG "\n";
print LOG "===start.$date\n";
print LOG "USERID\:$usermail=SIZE\:$size===STATUS\:$buf===SUBJECT\:$sub=======FROM\:$from1=======send\:$bytes_sent bytes\n";
#print LOG "$xml\n";
#print LOG "$mailcont\n";
print LOG "===end.$date $mid\n";

close(SOCK);
close(LOG);
}
}

sub die_fatal {
    open DIE,">>$log";
    print DIE "@_";
    close DIE;
}

sub alrm_fatal {
    $buf = "DELAY_ERROR";
}

