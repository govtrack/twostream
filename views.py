# -*- coding: utf-8 -*-
from django.http import HttpResponse, Http404
from django.core.urlresolvers import resolve
from django.template import Template, Context, RequestContext
from django.views.decorators.cache import cache_control
from django.contrib.messages import get_messages

import json

head_template_mime_type = "application/javascript"
head_template = Template("""
$(document).ajaxSend(
	function(event, xhr, settings) {
		if (!this.crossDomain && !/^(GET|HEAD|OPTIONS|TRACE)$/.test(settings.type))
			xhr.setRequestHeader("X-CSRFToken", "{{csrf_token|escapejs}}");
	}
);
var the_user = {{user_data|safe}};
var the_page = {{page_data|safe}};
var django_messages = {{django_messages|safe}};
""")

@cache_control(private=True, must_revalidate=True)
def user_head(request):
	# return information about the user
	user_data = None
	if request.user.is_authenticated():
		user_data = { "email": request.user.email }
		if hasattr(request.user, 'twostream_data'):
			d = request.user.twostream_data
			if callable(d):
				d = d()
			user_data.update(d)
		
	# call a view-specific custom function
	try:
		# get the view function corresponding to the path passed in the query string
		m = resolve(request.GET.get("path", request.GET.get("view", "")))
	except Http404:
		# 'path' might be empty --- the Django 500 template handler doesn't have access
		# to the request object and inadvertently will pass the empty string --- or something
		# invalid might be passed in, and we can just gracefully skip this part
		m = None
	page_data = None
	if m and hasattr(m.func, 'user_func'):
		try:
			page_data = m.func.user_func(request, *m.args, **m.kwargs)
		except Http404:
			# silently ignore, probably the main page was a 404 too
			pass

	# grab the messages framework messages
	def split_none(v):
		if v is None: return []
		return v.split(" ")
	messages = [
			{
				"message": m.message,
				"level": m.level,
				"level_tag": m.level_tag,
				"tags": split_none(m.tags),
				"extra_tags": split_none(m.extra_tags),
			}
			for m in
			sorted(get_messages(request), key = lambda m : m.level)
		]
	
	return HttpResponse(head_template.render(RequestContext(request, {
				"user_data": json.dumps(user_data),
				"page_data": json.dumps(page_data),
				"django_messages": json.dumps(messages)
				})), content_type=head_template_mime_type)
	
