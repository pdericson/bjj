"""
Convert Jenkins job definition to jenkins-job-builder yaml

Usage:
    bjj.py convertfile --path PATH...
    bjj.py convertjob --jenkins-url URL --job-regex REGEX [--user USER]
           [--password PASS]

Options:
    --path PATH         File to convert from
    --jenkins-url URL   Jenkins URL
    --job-regex REGEX   Regular expression to find jobs [Default: .*]
    --user USER         Jenkins user name
    --password PASS     Jenkins user's password or API token
"""
from docopt import docopt
import logging
from jenkinsapi.jenkins import Jenkins
import yaml
from jinja2 import Environment, PackageLoader
import xmltodict
import json
from pkg_resources import resource_string


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('bjj')


class literal_unicode(unicode):
    pass


def literal_unicode_representer(dumper, data):
    return dumper.represent_scalar(u'tag:yaml.org,2002:str', data, style='|')


yaml.add_representer(literal_unicode, literal_unicode_representer)


class FileIterator(object):
    def __init__(self, files):
        if isinstance(files, str):
            self.files = [files]
        else:
            self.files = files

    def __iter__(self):
        for xml_file in self.files:
            yield xml_file, self._et_from_file(xml_file)

    def __len__(self):
        return len(self.files)

    def _et_from_file(self, filename):
        with open(filename, 'r') as xml:
            x_dict = xmltodict.parse(xml)
        return x_dict


class NoTemplate(Exception):
    pass


class JenkinsIterator(object):
    def __init__(self, jenkins_url, user, passwd, regex):
        self.jenkins = Jenkins(jenkins_url, user, passwd)
        self.regex = regex

    def __iter__(self):
        for job_name in self.jenkins.jobs:
            # if regex matches
            # get job xml as string
            job_config = ""
            yield job_name, self._et_from_string(job_config)

    def _et_from_string(xml_string):
        return xmltodict.parse(xml_string)


class TemplatedConverter(object):
    def __init__(self, parts_path='parts'):
        self.env = Environment(loader=PackageLoader('bjj', parts_path),
                               trim_blocks=True,
                               lstrip_blocks=True,
                               line_statement_prefix='#',
                               line_comment_prefix='## ')

    def _parse_top_element(self, el_name, el_data):
        import pudb; pudb.set_trace()  # XXX BREAKPOINT
        part = resource_string(__name__, 'parts/' + el_name + '/base.part')
        tpl = self.env.from_string(part)
        result = tpl.render(**el_data[el])
        result += _parse_element(el_name, el_data)

    def _parse_element(self, el_name, el_data, path='parts'):
        result = []
        if not isinstance(el_data, dict):
            raise NoTemplate(path)
        for el in el_data:
            try:
                rel_path = path + '/' + el_name
                part = resource_string(__name__, rel_path + '/' + el + '.part')
                tpl = self.env.from_string(part)
                result.append(tpl.render(**el_data[el]))
            except IOError:
                result.append(self._parse_element(el, el_data[el], rel_path))

        return ''.join(result)

    def _convert(self, et, name):
        """
        Converts one job to yaml string
        """
        print json.dumps(et, indent=2)

        # Top level element is parsed here
        job = self._parse_element(et.keys()[0], et)

        for name, data in et['project'].iteritems():
            if not isinstance(data, dict):
                continue
            try:
                job += self._parse_top_element(name, data)
            except NoTemplate as tnf:
                logger.warning(
                    'Template "{}.part" not found. '
                    'Perhaps XML tag "{}" is not implemented yet'
                    .format(tnf.message, name))
        return job

    def convert(self, it):
        """
        Converts iterator of parsed XMLs to yaml files
        """
        # TODO: if iterator has multiple items - make job-group of them
        for name, et in it:
            yaml = self._convert(et, name)
            yaml_filename = name + '.yml'
            import pudb; pudb.set_trace()  # XXX BREAKPOINT
            with open(yaml_filename, 'w') as of:
                of.write(yaml)


def main():
    args = docopt(__doc__)

    if args['convertfile']:
        conv = FileIterator(args['--path'])
    else:
        conv = JenkinsIterator(
            args['--jenkins-url'],
            args['--user'],
            args['--password'],
            args['--job-regex']
        )

    TemplatedConverter().convert(conv)


if __name__ == '__main__':
    main()
