class Action(object):
    '''
    This class represents one instance of a Rule Engine Config rule action. Up to 5 actions per rule.
    '''
    def __init__(self, cfg: dict, engine_name: str, rule_name: str, fd_name: str, fd_group: str):
        if not cfg:
            raise ValueError('cfg cannot be None')

        if not rule_name:
            raise ValueError('rule_name cannot be None')

        if not 'type' in cfg:
            raise TypeError('engine rule actions type config cannot be empty')

        self.rulename = rule_name
        self.action_type = cfg['type']

        if self.action_type == 'RequestHeader' or self.action_type == 'ResponseHeader':
            ''' azure inconsistency. The cli calls this header-action, the portal calls this "Operator". We go with the cli naming '''
            self.header_action = cfg['header-action'] if 'header-action' in cfg else None
            self.header_name = cfg['header-name'] if 'header-name' in cfg else None
            self.header_value = cfg['header-value'] if 'header-value' in cfg else None
            if not self.header_value: raise ValueError('header-value cannot be null')
            if not self.header_name: raise ValueError('header-name cannot be null')
            if not self.header_action: raise ValueError('header-action cannot be null')
        if self.action_type == 'ForwardRouteOverride':
            self.backend_pool  = cfg['backend-pool'] if 'backend-pool' in cfg else None
            if not self.backend_pool:
                raise TypeError('backend-pool cannot be null when type is either ForwardRouteOverride')

            self.forward_path = cfg['forward-path'] if 'forward-path' in cfg else None
            if not self.forward_path:
                print('url rewrite is Disabled')

            self.forward_protocol = cfg['forward-protocol'] if 'forward-protocol' in cfg else 'Https'
            _caching = cfg['enable-caching'] if 'enable-caching' in cfg else 'False'
            if not _caching:
                self.enable_caching = 'Disabled'
            else:
                self.enable_caching = 'Enabled'

        if self.action_type == 'RedirectRouteOverride':
            self.redirect_type  = cfg['redirect-type'] if 'redirect-type' in cfg else 'Found'
            self.redirect_protocol = cfg['redirect-protocol'] if 'redirect-protocol' in cfg else 'Https'
            self.destination_host = cfg['destination-host'] if 'destination-host' in cfg else 'Preserve'
            self.destination_path = cfg['destination-path'] if 'destination-path' in cfg else 'Preserve'
            self.query_string = cfg['query-string'] if 'query-string' in cfg else 'Preserve'

        self.command = ['az', 'network', 'front-door'] # or new ['az', 'afd', 'rule']
        self.command.extend(['rules-engine', 'rule', 'action', 'add'])  #Override Route configuration is NOT supported in this command group,
        self.command.extend(['--rules-engine-name', engine_name])
        self.command.extend(['--name', self.rulename])
        self.command.extend(['-f', fd_name])
        self.command.extend(['-g', fd_group])

        self.command.extend(['--action-type', self.action_type])

        if self.action_type == 'RequestHeader' or self.action_type == 'ResponseHeader':
            self.command.extend(['--header-action', self.header_action])
            self.command.extend(['--header-name', self.header_name])
            self.command.extend(['--header-value', self.header_value])

        if self.action_type == 'ForwardRouteOverride':
            self.command.extend(['--backend-pool', self.backend_pool])
            if self.forward_path:
                self.command.extend(['--custom-forwarding-path', self.forward_path])
            self.command.extend(['--forwarding-protocol', self.forward_protocol])
            self.command.extend(['--caching', self.enable_caching])

        if self.action_type == 'RedirectRouteOverride':
            self.command.extend(['--redirect-protocol', self.redirect_protocol])
            self.command.extend(['--redirect-type', self.redirect_type])
            if not self.destination_host == 'Preserve':
                self.command.extend(['--custom-host', self.destination_host])
            if not self.destination_host == 'Preserve':
                self.command.extend(['--custom-path', self.destination_path])
            if not self.query_string == 'Preserve':
                self.command.extend(['--custom-query-string', self.query_string])

        #print(f'    --- ACTION {" ".join(self.command)}\n')

