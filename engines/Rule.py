from . import Condition
from . import Action
import subprocess
import traceback
import json

class Rule(object):
    '''
    This class represents one instance of a Rule Engine Config rule. Up to 25 rules per engine config
    conditions can be none, but actions must be > 0. From the user cfg, we actually do not need actions
    to be configured because we create a default noop action with every rule created. This allows us to 
    manage the rule better.
    Additionally the Override route configuration action type is NOT an allowed action-type when creating
    the rule. But it is valid in the action add api command. THIS SEEMS LIKE A AZURE API BUG.
    So for our case we always create a "noop" action as the action in the rule create command.
    The rule can only be created whilst specifying an Action.

    This is similar api behavior ad when adding backends to pools
    '''

    @classmethod
    def remove_rule_action(cls, rule: str, engine: str, action_type: str, index: int, fd_name: str, fd_group: str):
        """
        :return: True|False if action was removed
        """
        if not 'Header' in action_type:
            result = subprocess.run(
                ['az', 'network', 'front-door', 'rules-engine', 'rule', 'action', 'remove', '--name', rule, '--rules-engine-name', engine,
                 '-f', fd_name, '-g', fd_group, '--action-type', action_type], capture_output=True)
            cmd = ['az', 'network', 'front-door', 'rules-engine', 'rule', 'action', 'remove', '--name', rule, '--rules-engine-name', engine, '-f', fd_name, '-g', fd_group, '--action-type', action_type]
            print(f'\n{" ".join(cmd)}')

        else:
            result = subprocess.run(
                ['az', 'network', 'front-door', 'rules-engine', 'rule', 'action', 'remove', '--name', rule, '--rules-engine-name', engine,
                 '-f', fd_name, '-g', fd_group, '--action-type', action_type, '--index', str(index)], capture_output=True)
            cmd = ['az', 'network', 'front-door', 'rules-engine', 'rule', 'action', 'remove', '--name', rule, '--rules-engine-name', engine, '-f', fd_name, '-g', fd_group, '--action-type', action_type, '--index', str(index)]
            print(f'\n{" ".join(cmd)}')


        if result.stderr:
            print(f'warning: {result.stderr.decode("utf-8")}\nerror code: {result.returncode}')
            return False

        if result.returncode:
            print(f'error: {result.returncode}')
            return False

        return True


    @classmethod
    def remove_rule_condition(cls, rule: str, engine: str, index: int, fd_name: str, fd_group: str):
        """
        :return: True|False if condition was removed
        """
        result = subprocess.run(
            ['az', 'network', 'front-door', 'rules-engine', 'rule', 'condition', 'remove', '--name', rule, '--rules-engine-name', engine,
             '-f', fd_name, '-g', fd_group, '--index', str(index)], capture_output=True)
        cmd = ['az', 'network', 'front-door', 'rules-engine', 'rule', 'condition', 'remove', '--name', rule, '--rules-engine-name', engine, '-f', fd_name, '-g', fd_group, '--index', str(index)]
        print(f'\n{" ".join(cmd)}')

        if result.stderr:
            print(f'warning: {result.stderr.decode("utf-8")}\nerror code: {result.returncode}')
            return False
        return True

        if result.returncode:
            print(f'error: {result.returncode}')
            return False

    @classmethod
    def rule_exists(cls, rule: str, engine: str, fd_name: str, fd_group: str):
        """
        :return: True|False
        """
        result = subprocess.run(
            ['az', 'network', 'front-door', 'rules-engine', 'rule', 'show', '--name', rule, '--rules-engine-name', engine,
             '-f', fd_name, '-g', fd_group], capture_output=True)

        if result.stderr:
            print(f'warning: {result.stderr.decode("utf-8")}\nerror code: {result.returncode}')
            return False

        if result.returncode:
            print(f'error: {result.returncode}')
            return False

        return True

    @classmethod
    def get_all_rule_conditions(cls, rule: str, engine: str, fd_name: str, fd_group: str):
        """
        :return:
        """
        result = subprocess.run(
            ['az', 'network', 'front-door', 'rules-engine', 'rule', 'condition', 'list', '--name', rule, '--rules-engine-name', engine,
             '-f', fd_name, '-g', fd_group], capture_output=True)

        if result.stderr:
            print(f'warning: {result.stderr.decode("utf-8")}\nerror code: {result.returncode}')
            return {}

        if result.returncode:
            print(f'error: {result.returncode}')
            return False

        return json.loads(result.stdout)


    @classmethod
    def get_all_rule_actions(cls, rule: str, engine: str, fd_name: str, fd_group: str):
        """
        :return: requestHeaderActions[], responseHeaderActions[], routeConfigurationOverride{}
        """
        result = subprocess.run(
            ['az', 'network', 'front-door', 'rules-engine', 'rule', 'action', 'list', '--name', rule, '--rules-engine-name', engine,
             '-f', fd_name, '-g', fd_group], capture_output=True)

        if result.stderr:
            print(f'warning: {result.stderr.decode("utf-8")}\nerror code: {result.returncode}')
            return {}

        if result.returncode:
            print(f'error: {result.returncode}')
            return False

        data = json.loads(result.stdout)

        return data['requestHeaderActions'], data['responseHeaderActions'], data['routeConfigurationOverride']

    def __init__(self, action: str, cfg: dict, engine_name: str, priority: int, fd_name: str, fd_group: str):
        if not cfg:
            raise ValueError('cfg cannot be None')

        if not action:
            raise ValueError('rule action (create|update) must be specified')

        self.conditions = []
        self.actions = []
        self.engine_name = engine_name
        self.priority = priority

        self.name = next(iter(cfg))

        ''' TODO
        need to check actions and conditions for existing. Since they do not have names or other identifiers, we will remove and re-add
        all actions and conditions with the exception of the default noop action. This can be realized by header-name == route-manager-noop
        in a lookup of all actions.
        the remove actions and conditions should be done here BEFORE this class instance is returned
        Removing actions and conditions is done by index which is not exposed in a json properties or in the portal. It's the order
        that the action/conditions were created. So for actions, NOOP is always index 0. We need to create the index from the return
        lookup of all actions and conditions. Index corrosponds to the order returned in json.
        '''

        if self.rule_exists(self.name, self.engine_name, fd_name, fd_group):

            # REMOVE ACTIONS
            request, response, override = self.get_all_rule_actions(self.name, self.engine_name, fd_name, fd_group)

            if override:
                print('remove the routeConfigurationOverride action.....')
                if 'backendPool' in override:
                    result = self.remove_rule_action(self.name, self.engine_name, 'ForwardRouteOverride', 99, fd_name, fd_group)
                else:
                    result = self.remove_rule_action(self.name, self.engine_name, 'RedirectRouteOverride', 99, fd_name, fd_group)
            if request:
                index = len(request)
                if index: index-=1
                while index:
                    print(f'removing rule RequestHeader action index {index}, 0 is reserved for NOOP.....')
                    result = self.remove_rule_action(self.name, self.engine_name, 'RequestHeader', index, fd_name, fd_group)
                    index-=1
            if response:
                index = len(request)
                if index: index-=1
                while index >=0:
                    print(f'removing rule ResponseHeader action index {index}.....')
                    result = self.remove_rule_action(self.name, self.engine_name, 'ResponseHeader', index, fd_name, fd_group)
                    index-=1

            # REMOVE ALL CONDITIONS (there is not a NOOP condition since rules with no conditions is allowed by Azure) ....
            result = self.get_all_rule_conditions(self.name, self.engine_name, fd_name, fd_group)
            if result:
                index = len(result)
                if index: index-=1
                while index >=0:
                    print(f'removing rule condition index {index}.....')
                    result = self.remove_rule_condition(self.name, self.engine_name, index, fd_name, fd_group)
                    index-=1

        if 'conditions' in cfg:
            for c in cfg['conditions']:
                self.conditions.append(Condition.Condition(c, self.engine_name, self.name, fd_name, fd_group))
        if 'actions' in cfg:
            for a in cfg['actions']:
                self.actions.append(Action.Action(a, self.engine_name, self.name, fd_name, fd_group))

        self.command = ['az', 'network', 'front-door'] # or new ['az', 'afd', 'rule']
        self.command.extend(['rules-engine', 'rule', action])  #Override Route configuration is NOT supported in this command group??
        self.command.extend(['--rules-engine-name', self.engine_name])
        self.command.extend(['-f', fd_name])
        self.command.extend(['-g', fd_group])
        self.command.extend(['--name', self.name])
        self.command.extend(['--priority', str(self.priority)])
        if not action == 'update':
            self.command.extend(['--action-type', 'RequestHeader'])
            self.command.extend(['--header-action', 'Overwrite'])
            self.command.extend(['--header-name', 'route-manager-noop'])
            self.command.extend(['--header-value', 'no-rule-association'])

        #print(f'    --- RULE {" ".join(self.command)}\n')

