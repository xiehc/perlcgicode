#!/usr/bin/perl -w
#author xiehc

use strict;
use Net::LDAP;
use Digest::MD5 qw(md5_hex);
use Time::Local;
use LWP;
use Log::Log4perl qw(get_logger :levels);
use Log::Dispatch;
use Config::Properties;
use LWP::UserAgent;

open PROPS, "< /usr/local/apache2/cgi-bin/mail.properties" or die "unable to open configuration file";

my $properties = new Config::Properties();
$properties->load(*PROPS);

my $remote_key = $properties->getProperty('remote_key');
my $local_key = $properties->getProperty('local_key');
my $ldapServer = $properties->getProperty('ldap_server');
my $ldapPasswd = $properties->getProperty('ldap_passwd');
my $ips_str = $properties->getProperty('ips');
my $ldapServer_old = "192.168.0.1";

#log settings
Log::Log4perl->init_and_watch("/usr/local/apache2/cgi-bin/mail.conf", 60);
my $logger = get_logger("mail");
$logger->debug("debug begin-----");

print "Content-type: text/html\n\n";
my %param = &parse_form_data();

unless(validate_ip()){
    exit;
}
unless(validate_mac(%param)){
	exit;
}

my $domain  = $param{'domainName'};
my $mailstatus  = $param{'mailStatus'};
my $mailtype  = $param{'mailType'};
my $expiredate  = $param{'expireDate'};
my $spaceamount  = $param{'spaceAmount'};

$logger->debug("domain=$domain");
$logger->debug("mailstatus=$mailstatus");
$logger->debug("mailtype=$mailtype");
$logger->debug("expiredate=$expiredate");
$logger->debug("spaceamount=$spaceamount");


#connect to ldap
my $ldap = Net::LDAP->new("$ldapServer") or die "$@";
$ldap->bind( # bind to a directory with dn and password
            dn       => "cn=Manager,o=east",
            password => "$ldapPasswd"
           );


my $mesg = $ldap->search (  # perform a search
                               base   => "ou=$domain,o=east",
                               scope  => "one",
                               filter => "(primarykey=$domain)",
							   attrs => ['domainquota']
                             );
#$mesg->code && die $mesg->error;
my $t= $mesg->code;
$logger->debug("t=$t");
if ($t) {
#add by xiehc for handle old_db,090529
       &post2oldmaildbmodify($domain,$mailstatus,$mailtype,$expiredate,$spaceamount);

        #print "status=05\r\n";
        #print "error=domain not exists\r\n";
        #print "mac=", mac_gen(("status=05", "error=domain not exists"), $local_key), "\r\n";
        $ldap->unbind;
        $logger->debug($mesg->error);
        exit;
#add end,090529
}

my $count = $mesg -> count;


if($count == 1){
    my $entry = $mesg->entry(0);
	my $dn = $entry->dn;
	my $domainquota = $entry->get_value('domainquota');
	substr($domainquota, -1) = "";

	my %ReplaceHash = ();
	if($mailstatus == 0){
		$ReplaceHash{'mailstatus'} = 0;
	}elsif($mailstatus){
		$ReplaceHash{'mailstatus'} = $mailstatus;
	}
	$ReplaceHash{'mailtype'} = $mailtype if $mailtype;
	$ReplaceHash{'expiretime'} = dateToMs($expiredate) if $expiredate;
	if($spaceamount){
		if($mailstatus == 2){
			$ReplaceHash{'domainquota'} = ($domainquota - $spaceamount * 1024 * 1024 ) . "S";
		}else{
		
			$ReplaceHash{'domainquota'} = ($domainquota + $spaceamount * 1024 * 1024 ) . "S";
		}
	}

	my $result = LDAPmodifyUsingHash ( $ldap, $dn, \%ReplaceHash );

    unless($result->code){
		queryNewInfo($ldapServer, $domain);
	}else{
		print "status=99\r\n";
		print "error=", $result->error, "\r\n";
		print "mac=", mac_gen(("status=99", "error=".$result->error), $local_key), "\r\n";
	}
    

}else{
	print "status=05\r\n";
	print "error=domain not exists\r\n";
	print "mac=", mac_gen(("status=05", "error=domain not exists"), $local_key), "\r\n";
}

$ldap->unbind;


sub parse_form_data {
        my %form_data;
        my $name_value;
        my @name_value_pairs = split(/&/, $ENV{QUERY_STRING});

        if ($ENV{REQUEST_METHOD} eq 'POST') {
                my $query = "";
                read(STDIN, $query, $ENV{CONTENT_LENGTH}) == $ENV{CONTENT_LENGTH} or return undef;
                push(@name_value_pairs, split(/&/, $query));
        }

        foreach $name_value (@name_value_pairs) {
                my($name, $value) = split(/=/, $name_value);
                $name  =~ tr/+/ /;
                $name  =~ s/%([\da-f][\da-f])/chr(hex($1))/egi;
                $value = "" unless defined $value;
                $value =~ tr/+/ /;
                $value =~ s/%([\da-f][\da-f])/chr(hex($1))/egi;
                $form_data{$name} = $value;
        }
        return %form_data;
}

#sub validate_ip{
#        my $ip = $ENV{REMOTE_ADDR};
#        my $ipfile = "ip.txt";
#        open IPFILE, $ipfile or die "cannot open $ipfile:$! \n";
#        my %ips = ();
#        while(<IPFILE>){
#                chomp;
#                $ips{$_} ||= 1;
#        }
#        close IPFILE;
#
#        if($ips{$ip}){
#                return 1;
#        }else{
#                print "status=02\r\n";
#                print "error=Unauthorized ip:${ip}\r\n";
#				print "mac=", mac_gen(("status=02", "error=Unauthorized ip:${ip}"), $local_key), "\r\n";
#                return 0;
#        }
#}
sub validate_ip{
        my $ip = $ENV{REMOTE_HOST}?$ENV{REMOTE_HOST}:$ENV{REMOTE_ADDR};
        $logger->debug("$ip");
        my %ips = ();
		my @tmparr = split /,/, $ips_str;
		%ips = map {$_, 1} @tmparr;

        if($ips{$ip}){
                return 1;
        }else{
                print "status=02\r\n";
                print "error=Unauthorized ip:${ip}\r\n";
				print "mac=", mac_gen(("status=02", "error=Unauthorized ip:${ip}"), $local_key), "\r\n";
                return 0;
        }
}

sub validate_mac{
        (my %param) = @_;
        my $mac = $param{'mac'};
		$logger->debug("pass_mac=$mac");
        my @param_arr = ();
        my $private_key = $remote_key;
        foreach my $key (sort(keys %param)){
                if($key ne 'mac'){
                        push @param_arr, $key . '=' . $param{$key};
                }
        }
        my $param_str = join '&', @param_arr;
        $param_str .= $private_key;
        my $gen_mac = md5_hex($param_str);
        $logger->debug("gen_mac=$gen_mac");
		if($gen_mac eq $mac){
                return 1;
        }else{
                print "status=03\r\n";
                print "error=invalidate mac:$mac\r\n";
				print "mac=", mac_gen(("status=03", "error=invalidate mac:$mac"), $local_key), "\r\n";
                return 0;
        }
}

sub mac_gen{
        my $key = pop @_;
                my @param = @_;
        @param = sort @param;
        my $param_str = join '&', @param;

        $param_str .= $key;
    #    $logger->debug($param_str);
        return md5_hex($param_str);
}


sub LDAPmodifyUsingHash
 {
   my ($ldap, $dn, $whatToChange ) = @_;
   my $result = $ldap->modify ( $dn,
                                replace => { %$whatToChange }
                              );
   return $result;
 }

 sub dateToMs{
	(my $date) = @_;
	my ($year, $month, $day, $hour, $min, $sec) = split( /[^0-9]+/, $date );
	return timelocal($sec, $min, $hour, $day, $month-1, $year) * 1000;
}

sub post2oldmaildbmodify {
        my $domain = $_[0];
        my $mailstatus = $_[1];
        my $mailtype = $_[2];
        my $expiredate  = $_[3];
        my $spaceamount  = $_[4];

        chomp($domain);
        chomp($mailstatus);
        chomp($mailtype);
        chomp($expiredate);
        chomp($spaceamount);
       #my $local_key="0123456789abcdef";
        my $mac= mac_gen(("domainName=$domain","expireDate=$expiredate","mailStatus=$mailstatus","mailType=$mailtype","spaceAmount=$spaceamount"),$local_key);
#       $logger->debug("mymac=$mac");
       my $ua = LWP::UserAgent->new;

  #create a request
        my $req = HTTP::Request->new(POST => "http://$ldapServer_old/cgi-bin/modifymail.cgi");
        $req->content_type('application/x-www-form-urlencoded');
        $req->content("domainName=${domain}&mailStatus=${mailstatus}&mailType=${mailtype}&expireDate=${expiredate}&spaceAmount=${spaceamount}&mac=$mac");

  # Pass request to the user agent and get a response back
        my $res = $ua->request($req);

  # Check the outcome of the response
        if ($res->is_success) {
        my $recv = $res->content;
        print "$recv";
        print "1\n";
                              }
  else {
         print $res->status_line, "\n";
         print "$domain";
       }
                }

sub queryNewInfo{
        (my $server, my $domain) = @_;
		
		my $mac= mac_gen(("domainName=$domain"), $remote_key);
		$logger->debug("mac_gen=$mac");
        # Create a user agent object
        my $ua = LWP::UserAgent->new;
#       my $url = "http://${server}/cgi-bin/openmail_2.cgi?domainName=${domain}&userName=${user}&password=${passwd}";
#       print "<meta http-equiv=\"refresh\" content=\"1; url=${url}\">";
        # Create a request
        my $req = HTTP::Request->new(POST => "http://${server}/cgi-bin/querymail.cgi");
        $req->content_type('application/x-www-form-urlencoded');
        $req->content("domainName=${domain}&mac=${mac}");

        # Pass request to the user agent and get a response back
        my $res = $ua->request($req);

        # Check the outcome of the response
        if ($res->is_success) {
                print $res->content;
        }
        else {
                print "status=99\r\n";
                print "error=post request to mailserver fails\r\n";
				print "mac=", mac_gen(("status=99", "error=post request to mailserver fails"), $local_key), "\r\n";
        }

}

