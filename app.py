import html, re
from urllib.parse import quote as urlquote

from flask import Flask, redirect, request, Response
import config
import data

app = Flask('go')

@app.before_request
def before_request():
    data.open_db()

@app.teardown_request
def teardown_request(exception):
    data.close_db()

@app.errorhandler(Exception)
def show_exception(e):
    import traceback
    return make_error_response(''.join(
        traceback.format_exception(type(e), e, e.__traceback__)))

@app.route("/.well-known/acme-challenge/<token>")
def acme(token):
    """Proves to Letsencrypt that we own the domain go.wave.com."""
    key = find_acme_key(token)
    if key is None:
        abort(404)
    return key

@app.route('/')
def root():
    """SHows a directory of all existing links."""
    rows = [format_html('''
<tr>
<td class="name">go/<a href="/.edit?name={name_param}">{name}</a>
<td class="count">{count}
<td class="url"><a href="{url}">{url}</a>
</tr>''', name=name, url=url, name_param=urlquote(name), count=count)
    for name, url, count in data.get_all_links()]

    return Response('''
<!doctype html>
<link rel="stylesheet" href=".style.css">

<div class="corner">
  <form action="/.edit">
    <input name="name" placeholder="new shortcut">
  </form>
</div>
<h1>Where do you want to go/ today?</h1>

<div class="tip"><a href="#" onclick="document.getElementById('help').style.display='block'">Not working for you?</a></div>

<div id="help" class="tip">
Try typing "go/" into your address bar.
If it doesn't take you anywhere,
check to make sure you have an aText snippet set up for "go/".
<p>
As an alternative, you can configure Chrome
to let you type "go foo" instead of "go/foo" in the address bar.
To do this, go to Chrome Settings > Manage Search Engines,
then add a search engine with the keyword "go"
and URL "%s/%%s".
</div>

<table class="links">
<tr><th>shortcut</th><th>clicks</th><th>url</th>
%s
</table>
''' % (config.BASE_URL, ''.join(rows)))

@app.route('/<name>')
def go(name):
    """Redirects to a link."""
    url = data.get_url(name)
    if not url:
        return redirect('/.edit?name=' + urlquote(name))
    qs = (request.query_string or '').encode('utf-8')
    if qs:
        url += ('&' if '?' in url else '?') + qs
    data.log('redirect', name, url)
    data.update_count(name)
    return redirect(url)

@app.route('/.edit')
def edit():
    """Shows the form for creating or editing a link."""
    name = request.args.get('name', '').lstrip('.')
    url = data.get_url(name)
    if not name:
        return redirect('/')
    if not url:
        if not data.get_url(normalize(name)):
            name = normalize(name)  # default to normalized when creating
    original_name = message = ''
    if url:
        title = 'Edit go/' + name
        message = ' is an existing link. You can change it below.'
        original_name = name
    else:
        title = 'Create go/' + name
        message = " isn't an existing link. You can create it below."
    return Response(format_html('''
<!doctype html>
<link rel="stylesheet" href=".style.css">

<div class="corner"><a href="/">ALL THE LINKS!</a></div>
<h1>{title}</h1>

<div><a href="/{name_param}">go/{name_param}</a> {message}</div>
<form action="/.save" method="post">
<input type="hidden" name="original_name" value="{original_name}">
<table class="form"><tr valign="center">
  <td>go/<input name="name" value="{name}" placeholder="shortcut" size=10>
  <td><span class="arrow">\u2192</span>
  <td><input id="url" name="url" value="{url}" placeholder="URL" size=60>
</tr></table>
<div><input type=submit value="Save"></div>
<script>document.getElementById("url").focus()</script>
</form>
''', title=title, message=message, url=url or '',
     name=name, name_param=urlquote(name), original_name=original_name))

@app.route('/.save', methods=['POST'])
def save():
    """Creates or edits a link in the database."""
    original_name = request.form.get('original_name', '').lstrip('.')
    name = request.form.get('name', '').lstrip('.')
    url = request.form.get('url', '')
    if not name:
        return make_error_response('The shortcut must be made of letters.')
    if not (url.startswith('http://') or url.startswith('https://')):
        return make_error_response('URLs must start with http:// or https://.')
    try:
        if original_name:
            if not data.update_link(original_name, name, url):
                return make_error_response(
                    'Someone else renamed go/{}.'.format(original_name))
            data.log('update', name, url)
        else:
            data.add_link(name, url)
            data.log('create', name, url)
    except data.IntegrityError:
        return make_error_response('go/{} already exists.'.format(name))
    return redirect('/.edit?name=' + urlquote(name))

def normalize(name):
    """Keeps only lowercase letters and digits.  We don't require all shortcuts
    to be made only of these characters, but we encourage it by normalizing the
    shortcut name when prepopulating the creation form.

    We do this to give users confidence that they can hear a spoken link and
    just type it in without having to guess whether to use hyphens or
    underscores as word separators.  For special cases, it's still possible
    to make a shortcut name with punctuation by typing it into the name field.
    """
    return re.sub(r'[^a-z0-9]', '', name.lower())

@app.route('/.style.css')
def stylesheet():
    return app.send_static_file('style.css')


def find_acme_key(token):
    import os
    if token == os.environ.get("ACME_TOKEN"):
        return os.environ.get("ACME_KEY")
    for k, v in os.environ.items():
        if v == token and k.startswith("ACME_TOKEN_"):
            n = k.replace("ACME_TOKEN_", "")
            return os.environ.get("ACME_KEY_{}".format(n))

def make_error_response(message):
    """Makes a nice error page."""
    return Response(format_html('''
<!doctype html>
<link rel="stylesheet" href=".style.css">

<div class="corner"><a href="/">all links</a></div>
<div>Oh poo. <pre>{message}</pre></div>
''', message=message))

def format_html(template, **kwargs):
    """Like format(), but HTML-escapes all the parameters."""
    return template.format(
        **{key: html.escape(str(value)) for key, value in kwargs.items()})
