twostream
=========

Django 1.7+ middleware that makes it easy to mark certain pages as being cachable at the HTTP server level while still being able to fetch user-specific content through AJAX.

There are many ways to do caching. This one I find structurally simple. Usage comes in two parts:

1) This app provides a decorator named `@anonymous_view` to be applied to views that generate same output no matter who is accessing it. These views are thus safe to cache. To protect you by clearing all information in the HttpRequest that might be user-specific (including session, cookies, etc.) It also marks the HttpResponse as cachable by your HTTP server (if your server is configured to do that).

2) The app provides a snippet to include in your `<head>` tag to fetch user-specific information (if the user is logged in, page-specific content) and set a CSRF variable on all jQuery AJAX requests. This way, on pages marked with `@anomyous_view`, you can still display user-specific content and make AJAX calls.

Installation / Middleware
-------------------------

Clone this directory into a directory named `twostream` inside your project. Add it to your `settings.py`:

	INSTALLED_APPS = (
		...
		'twostream',
		...
	)

Also make sure you have:

	TEMPLATE_CONTEXT_PROCESSORS = (
			...
			'django.core.context_processors.request',
			...
	)

(Note that you must not have the `SESSION_SAVE_EVERY_REQUEST` setting set to True. The default is False, so unless you've changed it you are OK.)

Once the app is installed, all views by default apply the following headers to HttpResponses to prevent caching:

	Pragma: no-cache
	Cache-Control: no-cache, no-store, must-revalidate

But when all of these are met:

	* the `@anomyous_view` decorator is applied to a view
	* it is a GET or HEAD request
	* and the `DEBUG` setting is False

then a different set of headers are sent to flag that the request is cacheable:

	Cache-Control: public

Decorator
---------

Add the `@anonymous_view` deocrator to all views that should be cached:

	from twostream.decorators import anonymous_view

	@anonymous_view
	def myview(request, ...):
		# your view here

The decorator protects you from accidentally caching something specific to the user requesting the page by:

	* clearing `request.COOKIES` and `request.session`
	* setting `request.user` to a new AnonymousUser instance
	* clearing HTTP headers from `request.META` except SERVER_NAME, SERVER_PORT, HTTPS, wsgi.url_scheme, SERVER_PROTOCOL, HTTP_HOST, REQUEST_METHOD, REQUEST_URI, DOCUMENT_URI, PATH_INFO, QUERY_STRING, CONTENT_LENGTH', and CONTENT_TYPE
	* preventing the generation of a CSRF token

Make sure your HTTP server caching varies on any of the retained headers as necessary and recognizes the HttpResponse cache headers to know which pages to cache.

REMOTE_ADDR is actually retained when the `DEBUG` setting is True and the REMOTE_ADDR is contained in the `INTERNAL_IPS` setting so that debug tools continue to work

The decorator also sets `request.anonymous` to True so you can tell what happened.

Also make sure that you don't use any request middleware that is somehow able to modify the response based on any of the HTTP headers that might have user information, since they are only cleared at the start of view processing. Request middleware will still see it.

HTTP Server Caching
-------------------

Configure your HTTP server or caching layer to cache appropriately. Here is how I do this in nginx when serving Django via uWSGI:

At the top of nginx.conf:

	uwsgi_cache_path  /path/to/cache/storage levels=1:2 keys_zone=mydomain.com:100m inactive=72h max_size=1g;

In the `server` block:

	uwsgi_cache mydomain.com;
	uwsgi_cache_key "$scheme$request_method$host$request_uri";
	uwsgi_cache_valid 200 1h;
	uwsgi_cache_valid 301 5m;
	uwsgi_cache_valid 404 60s;
	uwsgi_cache_valid any 5s;
	uwsgi_cache_use_stale timeout invalid_header updating;
	uwsgi_no_cache $arg_nocache;
	uwsgi_cache_bypass $arg_nocache;

Some notes:

	* Nginx is smart enough to look at the cache headers in the HTTP response from Django to figure out what responses to cache.
	* I'm caching normal responses for 1 hour and other sorts of responses (redirects, 404s) for other shorter amounts of time.
	* The presence of "nocache=1" in the URL's query string will block caching, which is nice for testing.

Head Tag and User-Specific Content
----------------------------------

In order to get user-sepecific information on anonymous pages, and/or to provide CSRF tokens for AJAX calls, add to your URLconf:

	url(r'^_twostream', include('twostream.urls')),

And in the `<head>` part of your base template or at the end of your `<body>` (to delay the script load) add:

	{% include "twostream/head.html" %}

which adds a `<script>` tag that generates code that looks a little like this:

	$(document).ajaxSend(function(event, xhr, settings) { if (!/^https?:.*/.test(settings.url)) xhr.setRequestHeader("X-CSRFToken", "THE CSRF TOKEN"); });
	var the_user = {
		"email": "users-email@address.com"
	};
	var the_page = {
	};
	var django_messages = [];

This part works with jQuery 1.8+.

`the_user` will be null if the user is not logged in. If the user is logged in and any middleware you have sets `request.user.twostream_data` to a dict, it will be merged into `the_user`.

`the_page` will be null by default. To load user-specific data on a per-page basis, add a helper function after your view that takes the same arguments as your view:

	from twostream.decorators import anonymous_view, user_view_for

	@anonymous_view
	def myview(request, ...):
		# your view here

	@user_view_for(myview)
	def myview_userdata(request, ....):
	    return {
	    	"moreinfo": request.user.blah(),
	    }

The returned dict from the user view function is returned in the JSON object `the_page` accessible from Javascript.

Django Messages Framework
-------------------------

The Django [messages framework](https://docs.djangoproject.com/en/dev/ref/contrib/messages/) provides a way to queue one-time messages for users. This app's head script (explained in the last section) also reads the user's latest messages and stores them in a client-side variable.

If you use the messages framework, you will need to display those messages. After the include tag, process the messages like this:

    {% include "twostream/head.html" %}
    <script>
      if (django_messages.length > 0) {
        for (var i = 0; i < django_messages.length; i++) {
          display_message(django_messages[i].level_tag, django_messages[i].message);
        }
      }
    </script>

Each entry in the `django_messages` array has all of the fields on the [Message class](https://docs.djangoproject.com/en/dev/ref/contrib/messages/#the-message-class).

