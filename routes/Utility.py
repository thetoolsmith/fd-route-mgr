import json
import sys
import time
import subprocess
import collections

def convert_from_unicode(data):
  if isinstance(data, str):
      return str(data)
  elif isinstance(data, collections.abc.Mapping):
      return dict(map(convert_from_unicode, data.items()))
  elif isinstance(data, collections.abc.Iterable):
      return type(data)(map(convert_from_unicode, data))
  else:
      return data

def execute(runcmd=[], fatal=False, show=False):
    if show:
      print(f'running command in execute(): {runcmd}')

    _exec = subprocess.run(runcmd, universal_newlines=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    result = _exec.stdout
    err = _exec.stderr
    if err and ('is in preview' not in err):
        #print(f'warning: {err}')
        if fatal:
            raise RuntimeError(f'Failed: {runcmd}')
        else:
            return False, err 
    if result:
        output = convert_from_unicode(json.loads(result))
        if len(output) >= 1 and show:
            print(output)
        return True, output

    return True, None


def provisioning_needed(fdname: str, fdgroup: str, frontend: str, newssl_config: dict):
    print('lookup existing custom cert configuration....')

    command = ['az']
    command.extend(['network', 'front-door', 'frontend-endpoint', 'show',  '-g', fdgroup])
    command.extend(['--name', frontend])
    command.extend(['--front-door-name', fdname])

    result = subprocess.run(command, capture_output=True, timeout=120, text=True)
    ssl_config = {}

    try:
        ssl_config = json.loads(result.stdout)["customHttpsConfiguration"]
        ssl_config = ssl_config if ssl_config else {}
    except Exception as e:
        print(f'failed to get current ssl config for {frontend}: {str(e)}')
        return False

    current_ssl_config = {
        "secret_name": ssl_config["secretName"] if 'secretName' in ssl_config else None,
        "secret_version": ssl_config["secretVersion"] if 'secretVersion' in ssl_config else None,
        "minimum_tls": ssl_config["minimumTlsVersion"] if 'minimumTlsVersion' in ssl_config else None,
        "vault_id": ssl_config["vault"]["id"] if 'vault' in ssl_config and 'id' in ssl_config['vault'] else None
    }

    if current_ssl_config == newssl_config:
        return False

    return True


def cert_provisioning_status(fdname: str, fdgroup: str, frontend: str, timeout: int, desired_status: str):
    current_status = None
    sys.stdout.flush()

    print(f'timeout set to {(timeout / 60)} minutes')

    command = ['az']
    command.extend(['network', 'front-door', 'frontend-endpoint', 'wait',  '--timeout', str(timeout), '-g', fdgroup])
    command.extend(['--name', frontend])
    command.extend(['--front-door-name', fdname])
    command.extend(['--custom', '"customHttpsProvisioningState!=\'Enabling\'"'])

    _exec = subprocess.Popen(" ".join(command), shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    result, err = _exec.communicate()

    print('cert provisioning process has completed, getting status....')

    command = ['az']
    command.extend(['network', 'front-door', 'frontend-endpoint', 'show',  '-g', fdgroup])
    command.extend(['--name', frontend])
    command.extend(['--front-door-name', fdname])

    try:
        result = subprocess.run(command, capture_output=True, timeout=120, text=True)
    except Exception as e:
        print(f'failed to get frontend {frontend} config: {str(e)}')
        return False, None

    current_status = json.loads(result.stdout)["customHttpsProvisioningState"]

    if current_status != desired_status:
        return False, current_status
    else:
        return True, current_status


def assert_command_succeeded(result: subprocess.CompletedProcess, error_msg: str):
    assert result.returncode == 0, f'{error_msg}\nstderr:\n{result.stderr}'
