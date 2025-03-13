#!/usr/bin/env python3
'''
This tool is used to provision front door frontends, routing rules, pools, backends, probes and load balance configs

The input is a path to a config file with a structured yaml scheme
See /env/FrontdoorRouteManagerExample.cfg for details
'''
import os
import sys
import yaml
import argparse
from engines import Engine
from routes import Frontend, Pool, Rule
from routes import Utility as util

class EngineAssociation(object):
    def __init__(self, rule: str, engine: str, fd_name: str, fd_group: str):
        ''' link a rule engine to a rule '''
        self.command = ['az', 'network', 'front-door']
        self.command.extend(['routing-rule', 'update'])
        self.command.extend(['--front-door-name', fd_name])
        self.command.extend(['--resource-group', fd_group])
        self.command.extend(['--name', rule])
        self.command.extend(['--rules-engine', engine])

class Backend(object):
    def __init__(self, pool: str, endpoint: dict, fd_name: str, fd_group: str):
        ''' endpoint param was updated to dictionary 02/02/2021 '''
        self.action = 'add'
        self.command = ['az', 'network', 'front-door']
        self.command.extend(['backend-pool', 'backend', self.action])
        self.command.extend(['--front-door-name', fd_name])
        self.command.extend(['--resource-group', fd_group])
        self.command.extend(['--pool-name', pool])
        self.command.extend(['--address', next(iter(endpoint))])
        if 'host-header' in endpoint and endpoint['host-header']:
            self.command.extend(['--backend-host-header', endpoint['host-header']])

class BackendRemove(object):
    '''
    TBD..  this won't work because we need to know the index of the backend and it;s not available in portal or show command.
    This is a BUG in frontdoor api
    so we have no choice but to remove duplicate backends if found because we cannot remove the pool since rule engines and rules are associated.
    '''
    def __init__(self, pool, endpoint, fd_name, fd_group):
        self.action = 'remove'
        self.command = ['az', 'network', 'front-door']
        self.command.extend(['backend-pool', 'backend', self.action])
        self.command.extend(['--front-door-name', fd_name])
        self.command.extend(['--resource-group', fd_group])
        self.command.extend(['--pool-name', pool])

class Route(object):
    '''
    This represents the default routes. The RulesEngine class represents additonal configuration that 
    may or may not override these depending on the Action in each rule in each engine config.
    ref: https://docs.microsoft.com/en-us/azure/frontdoor/front-door-rules-engine
    '''
    def __init__(self, cfg, fd_name, fd_group):
        if not cfg:
            raise ValueError('cfg cannot be None')
        self.frontends = []
        self.pool = None
        self.rule = None
        self.fatal = cfg['fatal'] if 'fatal' in cfg else False

        if not 'frontends' in cfg:
            raise TypeError('frontends config cannot be empty')
        frontend_names = []

        for frontend_cfg in cfg['frontends']:
            fe_name = None
            for k,v in frontend_cfg.items():
                if not fe_name:
                    fe_name = k
                    frontend_names.append(k)
                break
            self.frontends.append(Frontend.Frontend(frontend_cfg, fe_name, fd_name, fd_group))

        if 'backend-pool' in cfg and cfg['backend-pool']:
            self.pool = Pool.Pool(cfg['backend-pool'], fd_name, fd_group)

        _rulename = None
        if isinstance(cfg, dict):
            for k,v in cfg.items():
                if not _rulename: _rulename = k
                break
        if 'backend-pool' in cfg and cfg['backend-pool']:
            self.rule = Rule.Rule(cfg, _rulename, frontend_names, self.pool.name, fd_name, fd_group)
        else:
            self.rule = Rule.Rule(cfg, _rulename, frontend_names, None, fd_name, fd_group)


if __name__ == "__main__":

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '--config',
    required=False,
    help="path/filename",
    default='FrontdoorMiscRoutes.cfg')

  parser.add_argument(
    '--verbose',
    help="enable console verbose output",
    action='store_true')

  parser.add_argument(
    '--veryverbose',
    help="enable console very verbose output",
    action='store_true')

  parser.add_argument(
    '--whatif',
    help="do not process anything",
    action='store_true')

  _args = vars(parser.parse_args())

  if not os.path.isfile(_args['config']):
      print(f'config {_args["config"]} not found, clean exit')
      sys.exit(0)

  script_error_status = 0

  with open(_args['config']) as file:
    config = yaml.load(file, Loader=yaml.FullLoader)

    rule_list = config['routing-rules']
    
    if not 'front-door-name' in config:
        raise TypeError('missing frontdoor name config')

    if not 'front-door-group' in config:
        raise TypeError('missing frontdoor group config')

    frontdoor_name = config['front-door-name']
    frontdoor_group = config['front-door-group']

    print('\nprocess routes......')

    found = []
    rule_seq = []
    for route in rule_list:
        if not route in found:
            found.append(route)
            rule_seq.append(route)
    for route_cfg in rule_seq:
        route = Route(route_cfg, frontdoor_name, frontdoor_group)

        print(f'\nROUTE RULE NAME --- {route.rule.name}')

        # PROCESS FRONTENDS
        for frontend in route.frontends:
            if frontend.create_frontend:
                print(f'creating frontend {frontend.name}, please wait ........')
                if _args['verbose']: print(f'\n{" ".join(frontend.command)}')
                if not _args["whatif"]:
                    success, result = util.execute(frontend.command)
                    if not success or not result:
                        print(f'command returned with:\n{result}')
                        if not 'already exists' in result and route.fatal:
                            raise RuntimeError(f'failed to create frontend {frontend.name}')
                    if _args['veryverbose']: print(result)

            if frontend.enable_ssl:
                #Is cert provisioning needed? the cli is NOT idempotent when specifying custom certs.
                #It will remove and recreate the cert on the frontend if we just call enable-ssl.
                #So we check to see if the metadata is already what we want to it to be
                _provision_cert = True

                if frontend.is_custom_cert:
                    newssl_config = {
                        "secret_name": frontend.secret_name,
                        "secret_version": None if 'Latest' == frontend.secret_version else frontend.secret_version,
                        "minimum_tls": str(frontend.tls_version),
                        "vault_id": frontend.vault_id
                    }

                    _provision_cert = util.provisioning_needed(
                                          frontdoor_name,
                                          frontdoor_group,
                                          frontend.name,
                                          newssl_config)

                if _provision_cert:
                    print(f'\nenabling ssl on {frontend.name}, please wait ......')
                    if not _args["whatif"]:
                        success, result = util.execute(frontend.ssl_command)
                        if not success or not result:
                            print(f'command returned with:\n{result}')
                            if not 'already exists' in result and route.fatal:
                                raise RuntimeError(f'failed to create frontend {frontend.name}')
                        if _args['veryverbose']: print(result)

                    # A timeout of 3600 matches the front door designer UI which states that certificate provisioning
                    # can take an hour. Another hour is added to account for the domain validation step when using
                    # Front Door managed certificates.
                    result, status = util.cert_provisioning_status(frontdoor_name, frontdoor_group, frontend.name, 7200, 'Enabled')
                    if result:
                        print(f'\n*** cert provisioning for frontend {frontend.name} succeeded with status {status} ***\n')
                    else:
                        print(f'\n*** CERT PROVISIONING FOR FRONTEND {frontend.name} FAILED with status {status} ***\n')
                        script_error_status = 1
                else:
                    print('cert provisioning not needed, current config is good!')

        # PROCESS BACKEND POOL
        if route.pool and route.pool.create_pool:
            if _args['verbose'] and route.pool.probe.command:
                print(f'\n{" ".join(route.pool.probe.command)}')
            if route.pool.probe.action and not _args["whatif"]:
                print(f'creating probe {route.pool.probe.name}, please wait ...')
                success, result = util.execute(route.pool.probe.command)
                if not success or not result:
                    print(f'command returned with:\n{result}')
                    if not 'already exists' in result and route.fatal:
                        raise RuntimeError(f'failed to create probe {route.pool.probe.name}')
                if _args['veryverbose']: print(result)

            if route.pool.loadbalancing.action and not _args["whatif"]:
                print(f'creating load balancing {route.pool.loadbalancing.name}, please wait ...')
                success, result = util.execute(route.pool.loadbalancing.command)
                if not success or not result:
                    print(f'command returned with:\n{result}')
                    if not 'already exists' in result and route.fatal:
                        raise RuntimeError(f'failed to create loadbalancing {route.pool.loadbalancing.name}')
                if _args['veryverbose']: print(result)

            if _args['verbose'] and route.pool.command:
                print(f'\n{" ".join(route.pool.command)}')

            if not _args["whatif"]:
                print(f'creating pool {route.pool.name}, please wait ...')
                print(f'\ncmd: {" ".join(route.pool.command)}')
                success, result = util.execute(route.pool.command, False, True)
                if not success or not result:
                    print(f'command returned with:\n{result}')
                    if not 'already exists' in result and route.fatal:
                        raise RuntimeError(f'failed to create pool {route.pool.name}')
                if _args['veryverbose']: print(result)

                #BACKEND PROCESSING
                _command = ['az', 'network', 'front-door']
                _command.extend(['backend-pool', 'show'])
                _command.extend(['--front-door-name', frontdoor_name])
                _command.extend(['--resource-group', frontdoor_group])
                _command.extend(['--name', route.pool.name])

                success, result = util.execute(_command)
                _existing_backends = []

                for be in result['backends']:
                    _existing_backends.append(be['address'])
                if _args['verbose']:
                    print(f'existing backends: {_existing_backends}')

                for endpoint in route.pool.backends:
                    if not next(iter(endpoint)) in _existing_backends:
                        print(f'adding backend {next(iter(endpoint))}')
                        backend = Backend(route.pool.name, endpoint, frontdoor_name, frontdoor_group)
                        if _args['verbose']: print(f'\n{" ".join(backend.command)}')
                        if backend.action and not _args["whatif"]:
                            print(f'creating pool backend {next(iter(endpoint))}, please wait ...')
                            success, result = util.execute(backend.command)
                            if not success or not result:
                                print(f'command returned with:\n{result}')
                                if not 'already exists' in result and route.fatal:
                                    raise RuntimeError(f'failed to add backend {next(iter(endpoint))} to pool {route.pool.name}')
                            if _args['veryverbose']: print(result)

        else:
            if route.pool:
                print(f'Using existing backend pool {route.pool.name}.....')

        # PROCESS RULE
        if route.rule.ruletype and route.rule.action and not _args["whatif"]:
            print(f'debug: rule type? {route.rule.ruletype} action? {route.rule.action}')
            print(f'creating rule {route.rule.name}, please wait .....')
            if _args['verbose']: print(f'{" ".join(route.rule.command)}')
            success, result = util.execute(route.rule.command)
            if not success or not result:
                print(f'command returned with:\n{result}')
                if not 'already exists' in result and route.fatal:
                    raise RuntimeError(f'failed to create rule {route.rule.name}')
            if _args['veryverbose']: print(result)

    # RULES ENGINE CONFIG
    print('\nprocess rules engines.....')

    engine_list = config['engine-rules'] if 'engine-rules' in config else []

    found = []
    engine_seq = []
    for engine in engine_list:
        if not engine in found:
            found.append(engine)
            engine_seq.append(engine)

    for engine_cfg in engine_seq:
        _engine_name = next(iter(engine_cfg))
        print(f'get Engine instance {next(iter(engine_cfg))}')
        engine = Engine(engine_cfg, _engine_name, frontdoor_name, frontdoor_group)
        rules = [r.name for r in engine.rules]
        print(f'creating the following rules in engine {engine.name}\n{[r.name for r in engine.rules]}')

        # PROCESS ENGINE RULES
        for r in engine.rules:
            if r.command and not _args ["whatif"]:
                if _args['verbose']: print(f'{" ".join(r.command)}')
                success, result = util.execute(r.command)
                if not success or not result:
                    print(f'command returned with:\n{result}')
                    raise RuntimeError(f'failed to create rule {r.name}')
                if _args['veryverbose']: print(result)

            # PROCESS RULE ACTIONS
            for a in r.actions:
                if a.command and not _args ["whatif"]:
                    if _args['verbose']: print(f'{" ".join(a.command)}')
                    success, result = util.execute(a.command)
                    if not success or not result:
                        print(f'command returned with:\n{result}')
                        raise RuntimeError(f'failed to create rule {r.name} action')
                    if _args['veryverbose']: print(result)

            # PROCESS RULE CONDITIONS
            for c in r.conditions:
                if c.command and not _args ["whatif"]:
                    if _args['verbose']: print(f'{" ".join(c.command)}')
                    success, result = util.execute(c.command)
                    if not success or not result:
                        print(f'command returned with:\n{result}')
                        raise RuntimeError(f'failed to create rule {r.name} condition')
                    if _args['veryverbose']: print(result)


    # LINK RULES ENGINE CONFIG
    print('\nassociating rules to engines.....')

    link_list = config['engine-associations'] if 'engine-associations' in config else []

    found = []
    link_seq = []
    for link in link_list:
        if not link in found:
            found.append(link)
            link_seq.append(link)

    for link_cfg in link_seq:
        engine_name = next(iter(link_cfg))
        print(f'Engine Association for engine: {engine_name}')
        rules = [r for r in link_cfg[engine_name]]
        for r in rules:
            engine_assoc = EngineAssociation(r, engine_name, frontdoor_name, frontdoor_group)
            if engine_assoc.command and not _args ["whatif"]:
                if _args['verbose']: print(f'{" ".join(engine_assoc.command)}')
                success, result = util.execute(engine_assoc.command)
                if not success or not result:
                    print(f'command returned with:\n{result}')
                    raise RuntimeError(f'failed to link rule {r} to engine {engine_name}')
                if _args['veryverbose']: print(result)


    sys.exit(script_error_status)
