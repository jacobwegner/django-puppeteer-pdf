from __future__ import absolute_import

import os
import re
import subprocess
import uuid
from copy import copy
from itertools import chain
from tempfile import NamedTemporaryFile

from django.core.files import File
from django.utils.encoding import smart_text

try:
    from urllib.request import pathname2url
    from urllib.parse import urljoin
except ImportError:  # Python2
    from urllib import pathname2url
    from urlparse import urljoin

import django
from django.conf import settings
from django.template import loader
from django.template.context import Context, RequestContext
from django.utils import six

NO_ARGUMENT_OPTIONS = ['-dhf', '--displayHeaderFooter', '-ht', '--printBackground', '-l', '--landscape',
                       '-h', '--help', '-V', '--version']


def _options_to_args(**options):
    """
    Converts ``options`` into a list of command-line arguments.
    Skip arguments where no value is provided
    For flag-type (No argument) variables, pass only the name and only then if the value is True
    """

    flags = []
    for name in sorted(options):
        value = options[name]
        formatted_flag = '--%s' % name if len(name) > 1 else '-%s' % name
        formatted_flag = formatted_flag.replace('_', '-')
        accepts_no_arguments = formatted_flag in NO_ARGUMENT_OPTIONS
        if value is None or (value is False and accepts_no_arguments):
            continue
        flags.append(formatted_flag)
        if accepts_no_arguments:
            continue
        flags.append(six.text_type(value))
    return flags


def puppeteer_to_pdf(input, output=None, **kwargs):
    """
    Converts html to PDF using page.pdf(options)
    https://github.com/GoogleChrome/puppeteer/blob/master/docs/api.md#pagepdfoptions

    input: file path or URL of the html to be converted.
    output: Optional output file path. If None, the output is returned.
    **kwargs: Passed to puppeteer page.pdf via options
    example usage:
        puppeteer_to_pdf(input='/tmp/example.html')
    """
    debug = getattr(settings, 'PUPPETEER_PDF_DEBUG', os.environ.get('PUPPETEER_PDF_DEBUG', settings.DEBUG))

    input = file_path(input)

    remove_output_file = False
    if not output:
        output = '/tmp/{0}.pdf'.format(uuid.uuid4())
        remove_output_file = True

    # Default options:
    options = getattr(settings, 'PUPPETEER_PDF_CMD_OPTIONS', None)
    if options is None:
        options = {'path': output}
    else:
        options = copy(options)
    options.update(kwargs)

    cmd = 'PUPPETEER_PDF_CMD'
    CHROME_LOCATION = 'puppeteer-pdf'  # default
    cmd = getattr(settings, cmd, os.environ.get(cmd, CHROME_LOCATION))

    ck_args = list(chain([cmd],
                         [input],
                         _options_to_args(**options)))

    sub_cmd = ' '.join(ck_args)
    if debug:
        print(sub_cmd)
    subprocess.call(sub_cmd, shell=True)

    if os.path.isfile(output):
        with open(output, 'rb') as f:
            data = File(f).read()

        if remove_output_file:
            os.unlink(output)
        return data
    else:
        return None


def file_path(path):
    """Return path with file protocol
    Ignore if it already starts with file path or http
    """
    if not path.startswith('http') and not path.startswith('file'):
        path = "file://{0}".format(path)
    return path


def convert_to_pdf(filename, header_filename=None, footer_filename=None, cmd_options=None):
    # Clobber header_html and footer_html only if filenames are
    # provided. These keys may be in self.cmd_options as hardcoded
    # static files.
    # The argument `filename` may be a string or a list. However, puppeteer_pdf
    # will coerce it into a list if a string is passed.
    cmd_options = cmd_options if cmd_options else {}

    if header_filename is not None:
        cmd_options['headerTemplate'] = file_path(header_filename)
        # with open(header_filename, 'r') as f:
        #     cmd_options['headerTemplate'] = "'{}'".format(f.read().replace('\n', ''))
    if footer_filename is not None:
        cmd_options['footerTemplate'] = file_path(footer_filename)
        # with open(footer_filename, 'r') as f:
        #     cmd_options['footerTemplate'] = "'{}'".format(f.read().replace('\n', ''))
    return puppeteer_to_pdf(input=filename, **cmd_options)


class RenderedFile(object):
    """
    Create a temporary file resource of the rendered template with context.
    The filename will be used for later conversion to PDF.
    """
    temporary_file = None
    filename = ''

    def __init__(self, template, context, request=None):
        debug = getattr(settings, 'PUPPETEER_PDF_DEBUG', os.environ.get('PUPPETEER_PDF_DEBUG', settings.DEBUG))

        self.temporary_file = render_to_temporary_file(
            template=template,
            context=context,
            request=request,
            prefix='puppeteer', suffix='.html',
            delete=(not debug)
        )
        self.filename = self.temporary_file.name

    def __del__(self):
        # Always close the temporary_file on object destruction.
        if self.temporary_file is not None:
            self.temporary_file.close()


def render_pdf_from_template(input_template, header_template, footer_template, context, request=None, cmd_options=None):
    # For basic usage. Performs all the actions necessary to create a single
    # page PDF from a single template and context.
    cmd_options = cmd_options if cmd_options else {}

    header_filename = footer_filename = None

    # Main content.
    input_file = RenderedFile(
        template=input_template,
        context=context,
        request=request
    )

    # Optional. For header template argument.
    if header_template:
        header_file = RenderedFile(
            template=header_template,
            context=context,
            request=request
        )
        header_filename = header_file.filename

    # Optional. For footer template argument.
    if footer_template:
        footer_file = RenderedFile(
            template=footer_template,
            context=context,
            request=request
        )
        footer_filename = footer_file.filename

    return convert_to_pdf(filename=input_file.filename,
                          header_filename=header_filename,
                          footer_filename=footer_filename,
                          cmd_options=cmd_options)


def content_disposition_filename(filename):
    """
    Sanitize a file name to be used in the Content-Disposition HTTP
    header.

    Even if the standard is quite permissive in terms of
    characters, there are a lot of edge cases that are not supported by
    different browsers.

    See http://greenbytes.de/tech/tc2231/#attmultinstances for more details.
    """
    filename = filename.replace(';', '').replace('"', '')
    return http_quote(filename)


def http_quote(string):
    """
    Given a unicode string, will do its dandiest to give you back a
    valid ascii charset string you can use in, say, http headers and the
    like.
    """
    if isinstance(string, six.text_type):
        try:
            import unidecode
        except ImportError:
            pass
        else:
            string = unidecode.unidecode(string)
        string = string.encode('ascii', 'replace')
    # Wrap in double-quotes for ; , and the like
    string = string.replace(b'\\', b'\\\\').replace(b'"', b'\\"')
    return '"{0!s}"'.format(string.decode())


def pathname2fileurl(pathname):
    """Returns a file:// URL for pathname. Handles OS-specific conversions."""
    return urljoin('file:', pathname2url(pathname))


def make_absolute_paths(content):
    """Convert all MEDIA files into a file://URL paths in order to
    correctly get it displayed in PDFs."""
    overrides = [
        {
            'root': settings.MEDIA_ROOT,
            'url': settings.MEDIA_URL,
        },
        {
            'root': settings.STATIC_ROOT,
            'url': settings.STATIC_URL,
        }
    ]
    has_scheme = re.compile(r'^[^:/]+://')

    for x in overrides:
        if not x['url'] or has_scheme.match(x['url']):
            continue

        if not x['root'].endswith('/'):
            x['root'] += '/'

        occur_pattern = '''["|']({0}.*?)["|']'''
        occurences = re.findall(occur_pattern.format(x['url']), content)
        occurences = list(set(occurences))  # Remove dups
        for occur in occurences:
            content = content.replace(occur,
                                      pathname2fileurl(x['root']) +
                                      occur[len(x['url']):])

    return content


def render_to_temporary_file(template, context, request=None, mode='w+b',
                             bufsize=-1, suffix='.html', prefix='tmp',
                             dir=None, delete=True):
    if django.VERSION < (1, 8):
        # If using a version of Django prior to 1.8, ensure ``context`` is an
        # instance of ``Context``
        if not isinstance(context, Context):
            if request:
                context = RequestContext(request, context)
            else:
                context = Context(context)
    # Handle error when ``request`` is None
    try:
        content = template.render(context)
    except AttributeError:
        content = loader.render_to_string(template, context)

    content = smart_text(content)
    content = make_absolute_paths(content)

    try:
        # Python3 has 'buffering' arg instead of 'bufsize'
        tempfile = NamedTemporaryFile(mode=mode, buffering=bufsize,
                                      suffix=suffix, prefix=prefix,
                                      dir=dir, delete=delete)
    except TypeError:
        tempfile = NamedTemporaryFile(mode=mode, bufsize=bufsize,
                                      suffix=suffix, prefix=prefix,
                                      dir=dir, delete=delete)

    try:
        tempfile.write(content.encode('utf-8'))
        tempfile.flush()
        return tempfile
    except:
        # Clean-up tempfile if an Exception is raised.
        tempfile.close()
        raise
