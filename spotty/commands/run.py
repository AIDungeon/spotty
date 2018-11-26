from argparse import ArgumentParser, Namespace
import re
import pystache
from spotty.commands.abstract_config_command import AbstractConfigCommand
from spotty.commands.writers.abstract_output_writrer import AbstractOutputWriter
from spotty.helpers.ssh import run_script
from spotty.providers.abstract_instance_manager import AbstractInstanceManager


class RunCommand(AbstractConfigCommand):

    name = 'run'
    description = 'Run a script from the configuration file inside the Docker container'

    def configure(self, parser: ArgumentParser):
        super().configure(parser)
        parser.add_argument('-s', '--session-name', type=str, default=None, help='tmux session name')
        parser.add_argument('-S', '--sync', action='store_true', help='Sync the project before running the script')
        parser.add_argument('script_name', metavar='SCRIPT_NAME', type=str, help='Script name')
        parser.add_argument('script_params', metavar='PARAMETER=VALUE', nargs='*', type=str, help='Script parameters')

    def _run(self, project_dir: str, config: dict, instance_manager: AbstractInstanceManager,
             args: Namespace, output: AbstractOutputWriter):
        sync_filters = config['project']['syncFilters']

        if args.instance_name and '=' in args.script_name:
            # fix argument values if at least two arguments provided and the second argument is a script parameter
            instance_name = None
            script_name = args.instance_name
            script_params = [args.script_name] + args.script_params
        else:
            instance_name = args.instance_name
            script_name = args.script_name
            script_params = args.script_params

        # check that the script exists
        if script_name not in config['scripts']:
            raise ValueError('Script "%s" is not defined in the configuration file.' % script_name)

        # get script parameters
        params = {}
        for param in script_params:
            match = re.match('(\w+)=(.*)', param)
            if not match:
                raise ValueError('Invalid script parameter: "%s"' % param)

            param_name, param_value = match.groups()
            if param_name in params:
                raise ValueError('Parameter "%s" defined twice' % param_name)

            params[param_name] = param_value

        # check that the instance is started
        if not instance_manager.is_running():
            raise ValueError('Instance "%s" is not started.' % instance_name)

        # sync the project with the instance
        if args.sync:
            instance_manager.sync(project_dir, sync_filters, output)

        # tmux session name
        session_name = args.session_name if args.session_name else 'spotty-script-%s' % script_name

        # replace script parameters
        script_content = pystache.render(config['scripts'][script_name], script_params)

        # run the script on the instance
        run_script(instance_manager.ip_address, instance_manager.ssh_user, instance_manager.ssh_key_path,
                   script_name, script_content, session_name, instance_manager.local_ssh_port)
