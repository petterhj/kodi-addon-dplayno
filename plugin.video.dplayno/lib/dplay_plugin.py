# Imports
from urllib import quote, unquote
from urlparse import parse_qs
from ast import literal_eval
from simpleplugin import Plugin, Params


# Class: DplayPlugin
class DplayPlugin(Plugin):
    # Get params
    @staticmethod
    def get_params(paramstring):
        raw_params = parse_qs(paramstring)
        params = Params()

        for key, value in raw_params.iteritems():
            paramvalue = value[0] if len(value) == 1 else value
            
            if key == 'api_params':
                # Evaluate api call parameters as a dictionary
                paramvalue = literal_eval(unquote(paramvalue))

            params[key] = paramvalue

        return params

    
    # Get url
    def get_url(self, plugin_url='', **kwargs):
        # Quote api call parameters
        if 'api_params' in kwargs:
            kwargs['api_params'] = quote(str(kwargs['api_params']))

        # Super
        return super(DplayPlugin, self).get_url(plugin_url, **kwargs)

    
    # Get resource
    def get_resource(self, file_name):
        return 'special://home/addons/%s/resources/%s' % (
            self.id,
            file_name
        )