class Condition(object):
    '''
    This class represents one instance of a Rule Engine Config rule conditions. Up to 10 conditions per rule.
    '''
    def __init__(self, cfg: dict, engine_name: str, rule_name: str, fd_name: str, fd_group: str):
        self.has_conditions = True
        if not cfg:
            print('no conditions IS ALLOWED')
            self.has_conditions = False
            return

        if not rule_name:
            raise ValueError('rule_name cannot be None')

        if not 'type' in cfg:
            raise TypeError('engine rule conditions type config cannot be empty')

        if not 'operator' in cfg:
            raise TypeError('engine rule conditions operator config cannot be empty')

        if not 'match-value' in cfg:
            raise TypeError('engine rule conditions match-value config cannot be empty')

        self.rulename = rule_name

        '''
        QueryString is the only condition implemented in practice as of 08/30/21
        supported_types all have the same fields. Others are specific and use different fields
        '''

        supported_types = ['QueryString','RequestBody','RequestFilename',
                           'RequestFilenameExtension','RequestPath','RequestMethod','RequestProtocol','RequestUri']

        self.negative_condition = False

        self.type = cfg['type']
        self.operator = cfg['operator']

        if self.operator[:3].lower() == 'not':
            self.negative_condition = True

        self.match_value = cfg['match-value']
        self.transform = cfg['transform'] if 'transform' in cfg else None #should check theser against valid values

        if not self.type in supported_types:
            raise TypeError(f'unknown engine rule condition type {self.type}')


        self.command = ['az', 'network', 'front-door'] # or new ['az', 'afd', 'rule', 'condition']
        self.command.extend(['rules-engine', 'rule', 'condition', 'add'])
        self.command.extend(['--name', self.rulename])
        self.command.extend(['--rules-engine-name', engine_name])
        self.command.extend(['-f', fd_name])
        self.command.extend(['-g', fd_group])
        self.command.extend(['--match-variable', self.type])

        self.command.extend(['--operator', self.operator])
        self.command.extend(['--match-values', self.match_value])

        if self.negative_condition:
            self.command.extend(['--negate-condition', self.negative_condition.lower()])
        if self.transform:
            self.command.extend(['--transforms', self.transform])

        #print(f'    --- CONDITION {" ".join(self.command)}\n')

