import json
import os
import pathlib
import subprocess
import traceback

import dns
from dns import resolver

from routes.Utility import assert_command_succeeded


class Frontend(object):
    @classmethod
    def get_front_door_sp(cls):
        """
        :return: a dictionary containing the front door service principal's attributes
        """
        result = subprocess.run(
            ['az', 'ad', 'sp', 'show', '--id', 'ad0e1c7e-6d38-4ba4-9efd-0bc77ba9f037'], capture_output=True)
        assert_command_succeeded(result, f'failed to get Frontdoor service principal.')
        return json.loads(result.stdout)

    @classmethod
    def get_front_door_id(cls, fdname, fdgroup):
        """
        :return: string resource id for a given frontdoor
        """
        result = subprocess.run(
            ['az', 'network', 'front-door', 'show', '--name', fdname, '-g', fdgroup], capture_output=True)

        assert_command_succeeded(result, f'failed to get Frontdoor ID.')
        return json.loads(result.stdout)

    @classmethod
    def get_frontend(cls, fdname, fdgroup, fename):
        result = subprocess.run(
            ['az', 'network', 'front-door', 'frontend-endpoint', 'show', '-f', fdname, '-g', fdgroup, '-n', fename],
            capture_output=True)
        assert_command_succeeded(result, f'Failed getting frontend {fename} in front door {fdname}')
        return json.loads(result.stdout)

    @classmethod
    def create_frontend_cname(cls, zonegroup, zonename, recordname, target):
        """
        :return: true | false
        """
        result = subprocess.run(
            ['az', 'network', 'dns', 'record-set', 'cname', 'create', '--name', recordname,
            '--resource-group', zonegroup, '--ttl', '300', '--zone-name', zonename, '--target-resource', target], capture_output=True)

        assert result.returncode == 0, f'failed to create cname.\nstderr:\n{result.stderr}'
        return result.stdout

    @classmethod
    def valid_dns_config_for_fd_cert(cls, frontend):
        """
        :param frontend: the frontend to validate
        if the frontend certificate type is set to FrontDoor, ensure that a CNAME mapping the frontend custom domain to
        the Front Door '.azurefd.net' hostname is configure as documented here:
        https://docs.microsoft.com/en-us/azure/frontdoor/front-door-custom-domain-https
        The document mentions that Front Door will fall back to email validation if a CNAME is not configured. We have
        found that, for at least some frontends, Front Door will get stuck in the domain validation
        state whem an attempt is made to configure a Front Door managed cert. The only way to rollback is to recreate
        the frontend (outage city; population: you). This check will cause the route manager to fail before attempting
        to create a Front Door managed cert with an unsupported DNS configuration.
        """

        if frontend.cert_type != 'FrontDoor' or not frontend.enable_ssl:
            print('skip DNS config validation when cert type is not front door, or ssl is disabled.')
            return

        print(f'validating DNS for custom domain {frontend.hostname}')
        fd_azure_net = f'{frontend.fd_name}.azurefd.net.'
        print(f'checking {frontend.hostname} mapped to {fd_azure_net}')
        valid = False
        try:
            answer = resolver.resolve(frontend.hostname, rdtype=dns.rdatatype.CNAME)
            answers = [str(a) for a in answer]
            print(f'{frontend.hostname} mapped to {", ".join(answers)}')
            valid = fd_azure_net in answers
        except:
            print(f'exception querying {frontend.hostname}')
            traceback.print_exc()

        if not valid:
            raise Exception(f'DNS is {"" if valid else "not "}valid for {frontend.hostname}')

    def __init__(self, cfg, name, fd_name, fd_group):
        if not cfg:
            raise ValueError('cfg cannot be None')

        self.name = name
        self.create_frontend = not cfg['exists'] if 'exists' in cfg else False
        self.secret_name = None
        self.secret_version = None
        self.vault_id = None
        self.fd_name = fd_name
        self.enable_ssl = cfg['enable-ssl'] if 'enable-ssl' in cfg else False

        if self.create_frontend:
            if not 'host-name' in cfg:
                raise TypeError('missing frontend host-name config')
            self.hostname = cfg['host-name']

            self.frontdoor_id = self.get_front_door_id(fd_name, fd_group)['id']
            assert self.frontdoor_id, f'failed to get Frontdoor ID for {fd_name}'

            #create cname here if need to
            create_cname = cfg['create_cname'] if 'create_cname' in cfg else False 

            if create_cname:
                if not 'zone_group' in cfg:
                    raise ValueError(f'missing resource group for {self.hostname}')
                _zone_group = cfg['zone_group']
                _cname = self.hostname.split('.')[0]
                _domain = self.hostname.split(_cname)[1][1:]
                result = self.create_frontend_cname(_zone_group, _domain, _cname, self.frontdoor_id)

            self.waf = cfg['waf-name'] if 'waf-name' in cfg else None
            self.sticky_sessions = cfg['sticky-sessions'] if 'sticky-sessions' in cfg else False
            self.session_ttl = cfg['session-ttl'] if 'session-ttl' in cfg else 60
            self.command = ['az', 'network', 'front-door']
            self.command.extend(['frontend-endpoint', 'create'])
            self.command.extend(['--front-door-name', fd_name])
            self.command.extend(['--resource-group', fd_group])
            self.command.extend(['--name', name])
            self.command.extend(['--host-name', self.hostname])
            if self.sticky_sessions:
                self.command.extend(['--session-affinity-enabled', 'true'])
                self.command.extend(['--session-affinity-ttl', str(self.session_ttl)])
            if self.waf:
                _waf_id = f'/subscriptions/{os.environ["ARM_SUBSCRIPTION_ID"]}/resourceGroups/{fd_group}/providers/Microsoft.Network/frontDoorWebApplicationFirewallPolicies/{self.waf}'
                self.command.extend(['--waf-policy', _waf_id])
        else:
            # the hostname is necessary for DNS validation
            front_end = self.get_frontend(fd_name, fd_group, name)
            self.hostname = front_end['hostName']

        # HTTPS (we should still allow user to apply SSL if the frontend already exists)
        self.tls_version = cfg['tls-version'] if 'tls-version' in cfg else '1.2'
        self.cert_type = cfg['certificate-type'] if 'certificate-type' in cfg else None
        self.valid_dns_config_for_fd_cert(self)
        if self.cert_type == 'AzureKeyVault':
            if not 'secret-name' in cfg:
                raise TypeError('missing secret-name config for certificate-type AzureKeyVault')
            if not 'secret-version' in cfg:
                raise TypeError('missing secret-version config for certificate-type AzureKeyVault')
            if not 'vault-id' in cfg:
                raise TypeError('missing vault-id config for certificate-type AzureKeyVault')

            # the service principal for front door may differ from subscription to subscription
            fd_sp_object_id = self.get_front_door_sp()['objectId']
            print(f'configuring access policy for front door service principal with object id {fd_sp_object_id}')
            _keyvault_name = pathlib.PurePath(f'{cfg["vault-id"]}').name
            _cmd = ['az', 'keyvault', 'set-policy', '-n', _keyvault_name]
            # set front door key vault access policy according to:
            # https://docs.microsoft.com/en-us/azure/frontdoor/front-door-custom-domain-https#grant-azure-front-door-access-to-your-key-vault
            _cmd.extend(['--certificate-permissions', 'get'])
            _cmd.extend(['--secret-permissions', 'get'])
            _cmd.extend(['--object-id', fd_sp_object_id])
            _result = subprocess.run(_cmd, universal_newlines=True, capture_output=True, timeout=120, text=True)
            if _result.returncode != 0:
                print(f'add frontdoor to keyvault access result {_result.returncode}')
            else:
                print('success add frontdoor to keyvault access')

            self.secret_name = cfg['secret-name']
            self.secret_version = cfg['secret-version']
            self.vault_id = cfg['vault-id']

        self.is_custom_cert = False

        if self.enable_ssl and not self.cert_type:
            raise TypeError('cannot enable ssl without specifiying certificate-type')

        if self.enable_ssl:
            self.ssl_command = ['az', 'network', 'front-door']
            self.ssl_command.extend(['frontend-endpoint', 'enable-https'])
            self.ssl_command.extend(['--front-door-name', fd_name])
            self.ssl_command.extend(['--resource-group', fd_group])
            self.ssl_command.extend(['--name', name])
            self.ssl_command.extend(['--certificate-source', self.cert_type])
            self.ssl_command.extend(['--minimum-tls-version', str(self.tls_version)])
            if self.cert_type == 'AzureKeyVault':
                self.is_custom_cert = True
                self.ssl_command.extend(['--secret-name', self.secret_name])
                if self.secret_version != 'Latest':
                    # do not include the --secret-version parameter to use the Latest version of a secret
                    self.ssl_command.extend(['--secret-version', self.secret_version])
                self.ssl_command.extend(['--vault-id', self.vault_id])
