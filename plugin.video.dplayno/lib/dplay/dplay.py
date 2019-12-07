#!/usr/bin/python
# -*- coding: utf-8 -*-

# Imports
import json
import logging
import requests

import elements
elements.TIMEZONE = 'Europe/Oslo'


# Constants
URL_BASE        = 'https://disco-api.dplay.no/%s'
URL_TOKEN       = 'token?realm=dplayno&deviceId=ce8b510da77effcdbb669855e4e949327b22d01a72d49077f46461f4661036e2&shortlived=true'
URL_USER        = 'users/me/'
URL_SHOWS       = 'content/shows/'
URL_VIDEOS      = 'content/videos/'
URL_PLAYBACK    = 'playback/videoPlaybackInfo/'
URL_CHANNELS    = 'content/channels/'


# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('[Dplay.%s]' % (__name__))


# Class: Dplay
class Dplay(object):
    # Init
    def __init__(self):
        # Session
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Android'

        # Obtain token
        logger.info('Obtaining token')
        
        token_data = self._request_json(URL_BASE % (URL_TOKEN))
        token_data = token_data[0].get('attributes', {})
        
        self.realm = token_data.get('realm')
        self.token = token_data.get('token')

        logger.info('Got token %s for realm %s' % (self.token, self.realm))

        # User
        user_data = self._request_json(URL_BASE % (URL_USER))
        self.user = elements.User(user_data[0])
        
        logger.info('Got user data: %s' % (self.user))


    # Prepare request parameters
    def _prepare_params(self, defaults={}, **kwargs):
        # Set default arguments and updated with provided
        arguments = {}
        arguments.update(defaults)
        arguments.update(kwargs)

        # Create request parameter dict
        params = {}

        if 'page_size' in arguments or 'page_number' in arguments:
            params.update({'page[size]': arguments.get('page_size', 100)}) # Accepts 1-100
            params.update({'page[number]': arguments.get('page_number', 1)})

        if arguments.get('include'):
            params.update({'include': ','.join(arguments.get('include'))})

        if arguments.get('filter'):
            for filter_param, filter_value in arguments['filter'].iteritems():
                params.update({'filter[%s]' % (filter_param): filter_value})

        if arguments.get('sort'):
            params.update({'sort': ','.join(arguments.get('sort'))})
        
        return params


    # Request JSON data from API
    def _request_json(self, url, default_params={}, **kwargs):
        # Get JSON from data source
        logger.info('Fetching data from %s' % (url))
        
        # Prepare params
        params = self._prepare_params(default_params, **kwargs)

        # print '-'*50
        # print json.dumps(params, indent=4)
        # print '-'*50

        if params:
            logger.info('> Params:')

            for param, value in params.iteritems():
                logger.info('  - %s=%s' % (param, value))

        # Request data
        r = self.session.get(url, params=params)
        
        logger.info('Requested %s (%d)' % (r.url, r.status_code))

        try:
            r.raise_for_status()

            logger.info('> Encoding: %s' % str(r.encoding))

            data = r.json()

        except Exception as e:
            logger.error('Request failed, %s' % (str(e)))

            return None, None

        else:
            # Return pre-parsed data
            return data['data'], data.get('included', [])


    # Shows
    def shows(self, **kwargs):
        '''
        Fetch video content from data source. Data is paginated. Accepts
        the following keyword arguments:
        
        page_size[int]  Request a limited number of pages
        page[int]       Request specific page of total requested
        filter[dict]    Dictionary containing filters as key value pairs
                            name.startsWith
        include[list]   Include extra
                            genres
                            tags
                            images
                            cache-meta
                            contentPackages
                            seasons
                            primaryChannel 
                            primaryChannel.images
        sort[list]      Sort criteria
                            views.lastMonth
        '''

        # Request
        data, included = self._request_json(URL_BASE % (URL_SHOWS), default_params={
            'page_size': 100,
            'page_number': 1,
            'include': ['genres', 'images']
        }, **kwargs)
            
        # Return show
        return [elements.Show(show, included=included, user=self.user) for show in data]
      
    
    # Show
    def show(self, show_id, **kwargs):
        '''
        Returns show details.
        
        show_id         Unique show ID (also accepts alternate_id)
        include         Include extra
                            genres
                            tags
                            images
                            cache-meta
                            contentPackages
                            seasons
                            primaryChannel 
                            primaryChannel.images
        '''

        # Request
        data, included = self._request_json(URL_BASE % (URL_SHOWS) + str(show_id), default_params={
            'include': ['genres', 'images', 'seasons']
        }, **kwargs)
            
        # Return show
        return elements.Show(data, included=included, user=self.user)


    # Videos
    def videos(self, **kwargs):
        '''
        Fetch video content from data source. Data is paginated. Accepts 
        
        page_size[int]  Request a limited number of pages
        page[int]       Request specific page of total requested
        filter[dict]    Dictionary containing filters as key value pairs
                            videoType=EPISODE,LIVE,FOLLOW_UP
                            show.id
                            seasonNumber
                            primaryChannel.id
        include[list]   Include extra
                            primaryChannel
                            primaryChannel.images
                            show,
                            show.images
                            genres
                            tags
                            images
                            cache-meta
                            provider
                            contentPackages
        sort[list]      Sort criteria
                            name
                            publishStart
                            publishEnd
                            episodeNumber
                            seasonNumber
                            views.lastDay
                            views.lastWeek
                            views.lastMonth
                            earliestPlayableStart
                            videoType
        '''

        # Request
        data, included = self._request_json(URL_BASE % (URL_VIDEOS), default_params={
            'page_size': 25,
            'page_number': 1,
            'include': ['images', 'genres', 'show']
        }, **kwargs)

        return [elements.Video(video, included=included, user=self.user) for video in data]
        

    # Playable
    def playable(self, video_id, **kwargs):
        ''' 
        Returns video playback details.
        '''

        # Request
        data, included = self._request_json(URL_BASE % (URL_PLAYBACK) + str(video_id), **kwargs)

        return elements.Playable(data) if data else None


    # Channels
    def channels(self, **kwargs):
        '''
        Fetch channel data.

        include[list]   Include extra
                            images
                            cache-meta
                            contentPackages
        '''

        # Request
        data, included = self._request_json(URL_BASE % (URL_CHANNELS), default_params={
            'page_size': 100,
            'page_number': 1,
            'include': ['images']
        }, **kwargs)
            
        # Return show
        return [elements.Channel(channel, included=included, user=self.user) for channel in data]


    # Channel
    def channel(self, channel_id, **kwargs):
        '''
        Returns show details.
        
        channel_id      Unique channel ID (also accepts alternate_id)
        include         Include extra
                            images
                            cache-meta
                            contentPackages
        '''

        # Request
        data, included = self._request_json(URL_BASE % (URL_CHANNELS) + str(channel_id), default_params={
            'include': ['images']
        }, **kwargs)
            
        # Return show
        return elements.Channel(data, included=included, user=self.user)