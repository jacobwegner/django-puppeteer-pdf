from __future__ import absolute_import

from re import compile
from tempfile import NamedTemporaryFile
import warnings

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.views.generic import TemplateView

from .utils import (content_disposition_filename, wkhtmltopdf)


class PDFResponse(HttpResponse):
    """HttpResponse that sets the headers for PDF output."""

    def __init__(self, content, mimetype=None, status=200,
                 content_type=None, filename=None, *args, **kwargs):

        if content_type is None:
            content_type = 'application/pdf'

        super(PDFResponse, self).__init__(content=content,
                                          mimetype=mimetype,
                                          status=status,
                                          content_type=content_type)
        self.set_filename(filename)

    def set_filename(self, filename):
        self.filename = filename
        if filename:
            filename = content_disposition_filename(filename)
            header_content = 'attachment; filename={0}'.format(filename)
            self['Content-Disposition'] = header_content
        else:
            del self['Content-Disposition']


class PdfResponse(PDFResponse):
    def __init__(self, content, filename):
        warnings.warn('PdfResponse is deprecated in favour of PDFResponse. It will be removed in version 1.',
                      PendingDeprecationWarning, 2)
        super(PdfResponse, self).__init__(content, filename=filename)


class PDFTemplateResponse(TemplateResponse, PDFResponse):
    """Renders a Template into a PDF using wkhtmltopdf"""

    def __init__(self, request, template, context=None, mimetype=None,
                 status=None, content_type=None, current_app=None,
                 filename=None, header_template=None, footer_template=None,
                 cmd_options=None, *args, **kwargs):

        super(PDFTemplateResponse, self).__init__(request=request,
                                                  template=template,
                                                  context=context,
                                                  mimetype=mimetype,
                                                  status=status,
                                                  content_type=content_type,
                                                  current_app=None,
                                                  *args, **kwargs)
        self.set_filename(filename)

        self.header_template = header_template
        self.footer_template = footer_template

        if cmd_options is None:
            cmd_options = {}
        self.cmd_options = cmd_options

    def render_to_temporary_file(self, template_name, mode='w+b', bufsize=-1,
                                 suffix='', prefix='tmp', dir=None,
                                 delete=True):
        template = self.resolve_template(template_name)
        context = self.resolve_context(self.context_data)
        content = template.render(context)
        tempfile = NamedTemporaryFile(mode=mode, bufsize=bufsize,
                                      suffix=suffix, prefix=prefix,
                                      dir=dir, delete=delete)
        try:
            tempfile.write(content)
            tempfile.flush()
            return tempfile
        except:
            # Clean-up tempfile if an Exception is raised.
            tempfile.close()
            raise

    @property
    def rendered_content(self):
        """Returns the freshly rendered content for the template and context
        described by the PDFResponse.

        This *does not* set the final content of the response. To set the
        response content, you must either call render(), or set the
        content explicitly using the value of this property.
        """
        debug = getattr(settings, 'WKHTMLTOPDF_DEBUG', False)

        cmd_options = self.cmd_options.copy()

        input_file = header_file = footer_file = None

        try:
            input_file = self.render_to_temporary_file(
                template_name=self.template_name,
                prefix='wkhtmltopdf', suffix='.html',
                delete=(not debug)
            )

            if self.header_template:
                header_file = self.render_to_temporary_file(
                    template_name=self.header_template,
                    prefix='wkhtmltopdf', suffix='.html',
                    delete=(not debug)
                )
                cmd_options.setdefault('header_html', header_file.name)

            if self.footer_template:
                footer_file = self.render_to_temporary_file(
                    template_name=self.footer_template,
                    prefix='wkhtmltopdf', suffix='.html',
                    delete=(not debug)
                )
                cmd_options.setdefault('footer_html', footer_file.name)

            return wkhtmltopdf(pages=[input_file.name], **cmd_options)
        finally:
            # Clean up temporary files
            for f in filter(None, (input_file, header_file, footer_file)):
                f.close()


class PDFTemplateView(TemplateView):
    """Class-based view for HTML templates rendered to PDF."""

    # Filename for downloaded PDF. If None, the response is inline.
    filename = 'rendered_pdf.pdf'

    # Filenames for the content, header, and footer templates.
    template_name = None
    header_template = None
    footer_template = None

    # TemplateResponse classes for PDF and HTML
    response_class = PDFTemplateResponse
    html_response_class = TemplateResponse

    # Command-line options to pass to wkhtmltopdf
    cmd_options = {
        # 'orientation': 'portrait',
        # 'collate': True,
        # 'quiet': None,
    }

    def __init__(self, *args, **kwargs):
        super(PDFTemplateView, self).__init__(*args, **kwargs)

        # Copy self.cmd_options to prevent clobbering the class-level object.
        self.cmd_options = self.cmd_options.copy()

    def get(self, request, *args, **kwargs):
        response_class = self.response_class
        try:
            if request.GET.get('as', '') == 'html':
                # Use the html_response_class if HTML was requested.
                self.response_class = self.html_response_class
            return super(PDFTemplateView, self).get(request,
                                                    *args, **kwargs)
        finally:
            # Remove self.response_class
            self.response_class = response_class

    def get_filename(self):
        return self.filename

    def get_cmd_options(self):
        return self.cmd_options

    def get_pdf_kwargs(self):
        warnings.warn('PDFTemplateView.get_pdf_kwargs() is deprecated in favour of get_cmd_options(). It will be removed in version 1.',
                      PendingDeprecationWarning, 2)
        return self.get_cmd_options()

    def get_context_data(self, **kwargs):
        context = super(PDFTemplateView, self).get_context_data(**kwargs)

        match_full_url = compile(r'^https?://')
        if not match_full_url.match(settings.STATIC_URL):
            context['STATIC_URL'] = 'http://' + Site.objects.get_current().domain + settings.STATIC_URL
        if not match_full_url.match(settings.MEDIA_URL):
            context['MEDIA_URL'] = 'http://' + Site.objects.get_current().domain + settings.MEDIA_URL

        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Returns a PDF response with a template rendered with the given context.
        """
        filename = response_kwargs.pop('filename', None)
        cmd_options = response_kwargs.pop('cmd_options', None)

        if issubclass(self.response_class, PDFTemplateResponse):
            if filename is None:
                filename = self.get_filename()
            if cmd_options is None:
                cmd_options = self.get_cmd_options()
            return super(PDFTemplateView, self).render_to_response(
                context=context, filename=filename,
                header_template=self.header_template,
                footer_template=self.footer_template,
                cmd_options=cmd_options,
                **response_kwargs
            )
        else:
            return super(PDFTemplateView, self).render_to_response(
                context=context,
                **response_kwargs
            )


class PdfTemplateView(PDFTemplateView): #TODO: Remove this in v1.0
    orientation = 'portrait'
    margin_bottom = 0
    margin_left = 0
    margin_right = 0
    margin_top = 0

    def __init__(self, *args, **kwargs):
        warnings.warn('PdfTemplateView is deprecated in favour of PDFTemplateView. It will be removed in version 1.',
                      PendingDeprecationWarning, 2)
        super(PdfTemplateView, self).__init__(*args, **kwargs)

    def get_cmd_options(self):
        return self.get_pdf_kwargs()

    def get_pdf_kwargs(self):
        kwargs = {
            'margin_bottom': self.margin_bottom,
            'margin_left': self.margin_left,
            'margin_right': self.margin_right,
            'margin_top': self.margin_top,
            'orientation': self.orientation,
        }
        return kwargs
