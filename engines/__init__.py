from . import Rule
import subprocess
import traceback
import json

from routes.Utility import assert_command_succeeded

class Engine(object):
    '''
    This class represents one instance of a Rule Engine Config. Frontdoor can have up to 10 rule
    engines.
    '''

    @classmethod
    def get_engine_rule(cls, engine, rule, fd_name, fd_group):
        """
        :return: string rule for given rule engine
        """
        result = subprocess.run(
            ['az', 'network', 'front-door', 'rules-engine', 'rule', 'show', '--name', rule, '--rules-engine-name', engine, '-f', fd_name, '-g', fd_group], capture_output=True)

        if result.stderr:
            _errstr = result.stderr.decode("utf-8").replace("'", "")
            if f'rule {rule} not found' in _errstr:
                return {}

        return json.loads(result.stdout)


    @classmethod
    def get_all_engine_rules(cls, engine, fd_name, fd_group):
        """
        :return: dict all rule name and priority in a given engine
        """
        result = subprocess.run(
            ['az', 'network', 'front-door', 'rules-engine', 'rule', 'list', '--name', engine,
             '-f', fd_name, '-g', fd_group, '--query', '[].{name:name,priority:priority}', '-o', 'json'], capture_output=True)

        if result.stderr:
            print(f'warning: {result.stderr.decode("utf-8")}')
            return {}

        existing_rules = {}

        for r in json.loads(result.stdout):
            existing_rules[r['name']] = r['priority']

        return existing_rules


    def __init__(self, cfg: dict, name: str, fd_name: str, fd_group: str):
        if not cfg:
            raise ValueError('cfg cannot be None')

        if not 'rules' in cfg:
            raise TypeError('engine config rules cannot be empty')

        self.name = name
        self.rules = []
        next_priority = 0

        existing_rules = self.get_all_engine_rules(self.name, fd_name, fd_group)

        if existing_rules:
            for k,v in existing_rules.items():
                if v > next_priority: next_priority = v

        noop_rule = {'routemanagerNOOP': None}

        if 'routemanagerNOOP' in existing_rules:
            self.rules.append(Rule.Rule('update', noop_rule, name, existing_rules['routemanagerNOOP'], fd_name, fd_group))
        else:
            next_priority+=1
            self.rules.append(Rule.Rule('create', noop_rule, name, next_priority, fd_name, fd_group))

        '''
        Azure api does no allow you to remove the rule from an engine if it is the only rule.
        therefore we create a noop rule (which will also have a required noop action)
        so we are able to remove and re-config all needed rules. The alternative would be to remove the engine.
        However to remove the engine we need to know all the associations which are applied at the routing rule api
        Frontdoor route manager follows this logic and specified engine associations at the routing rule configuration.
        '''

        for r in cfg['rules']:
            _rule = next(iter(r))
            if _rule in existing_rules:
                self.rules.append(Rule.Rule('update', r, name, existing_rules[_rule], fd_name, fd_group))
            else:
                next_priority+=1
                self.rules.append(Rule.Rule('create', r, name, next_priority, fd_name, fd_group))

