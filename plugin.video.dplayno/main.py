#!/usr/bin/python
# -*- coding: utf-8 -*-

# Imports
import string
import xbmc
import xbmcgui
import xbmcaddon
from urllib import quote

from lib.dplay import Dplay
from lib.dplay_plugin import DplayPlugin


# Plugin
plugin = DplayPlugin()


# Dplay 
dplay = Dplay()


# Action: Root
@plugin.action()
def root():
    ''' Display main menu items '''

    # Context menu
    context_menu = [
        ('Settings', 'Addon.OpenSettings(%s)' % (plugin.id)),
    ]


    # Main menu
    return [
        {
            'label': 'Programmer (A-Å)',
            'thumb': plugin.get_resource('icon_program.png'),
            'context_menu': context_menu,
            'url': plugin.get_url(action='shows_by_letter'),
        },
        {
            'label': 'Populære programmer (siste måned)',
            'thumb': plugin.get_resource('icon_program_favourite.png'),
            'context_menu': context_menu,
            'url': plugin.get_url(action='shows', api_params={
                'page_size': 50,
                'sort': ['views.lastMonth'],
            }),
        },
        {
            'label': 'Populære episoder (siste uke)',
            'thumb': plugin.get_resource('icon_video_favourite.png'),
            'context_menu': context_menu,
            'url': plugin.get_url(action='videos', api_params={
                'page_size': 25,
                'sort': ['views.lastWeek'],
            }),
        },
        {
            'label': 'Populære episoder (siste måned)',
            'thumb': plugin.get_resource('icon_video_favourite.png'),
            'context_menu': context_menu,
            'url': plugin.get_url(action='videos', api_params={
                'page_size': 25,
                'sort': ['views.lastMonth'],
            }),
        },
        {
            'label': 'Sist viste episoder',
            'thumb': plugin.get_resource('icon_video.png'),
            'context_menu': context_menu,
            'url': plugin.get_url(action='videos', api_params={
                'page_size': 50,
                'sort': ['-publishStart'],
            }),
        },
        {
            'label': 'Kanaler',
            'thumb': plugin.get_resource('icon_channels.png'),
            'context_menu': context_menu,
            'url': plugin.get_url(action='channels', api_params={}),
        },
    ]


# Action: Shows by letter
@plugin.action()
def shows_by_letter(params):
    return [{
        'label': letter,
        'url': plugin.get_url(action='shows', api_params={
            'filter': {'name.startsWith': letter}
        }),
    } for letter in [l for l in string.ascii_uppercase] + ['Æ', 'Ø', 'Å', '#']]


# Action: Shows
@plugin.action()
def shows(params):
    ''' Display list of shows '''

    # Get shows
    shows = dplay.shows(**params.api_params)

    items = [{
        'label': '%s [COLOR grey](%d)[/COLOR]' % (
            show.name if show.authorized else '[COLOR grey]%s[/COLOR]' % (show.name),
            show.video_count,
        ),
        'thumb': show.get_image_src('poster') or show.get_image_src('default'),
        'fanart': show.get_image_src('default'),
        'info': {
            'video': {
                'plot': show.description,
                'genre': ', '.join([g.name for g in show.genres if 'produksjon' not in g.name]),
                'aired': str(show.newest_episode_publish_start),
                'mpaa': ', '.join([p[0:1].upper() for p in show.packages])
            }
        },
        'is_authorized': show.authorized,
        'is_folder': True,
        'url': plugin.get_url(action='show', api_params={'show_id': show.id}),
    } for show in shows]

    # Filter
    if plugin.get_setting('hide_unavailable_shows'):
        items = [i for i in items if i.get('is_authorized', True)]

    return items


# Action: Show
@plugin.action()
def show(params):
    ''' Display list of show seasons '''

    # Get show details
    show = dplay.show(**params.api_params)

    # Return seasons (or flatten)
    # if show.get('season_count') > 1:
    return [{
        'label': '[COLOR %s]Sesong %d[/COLOR] [COLOR grey](%d)[/COLOR]' % (
            'white' if show.authorized else 'grey',
            season.season_number, 
            season.video_count
        ),
        'thumb': show.get_image_src('poster') or show.get_image_src('default'),
        'fanart': show.get_image_src('default'),
        'url': plugin.get_url(action='videos', api_params={
            'filter': {
                'show.id': show.id, 
                'seasonNumber': season.season_number
            }
        }),
    } for season in sorted(show.seasons, key=lambda s: s.season_number, reverse=plugin.get_setting('reverse_sort'))]


# Action: Videos
@plugin.action()
def videos(params):
    ''' Display list of videos '''

    # Get videos
    videos = dplay.videos(**params.api_params)

    items = [{        
        # 'label': '[COLOR %s]%s%s[/COLOR]' % (
        'label': '[COLOR %s]%s[/COLOR]' % (
            'white' if video.authorized else 'grey',
            # '%s: ' % (video.show.name) if video.show else '',
            video.full_name,
        ),
        'thumb': video.get_image_src('poster') or video.get_image_src('default'),
        'fanart': video.get_image_src('default'),
        'info': {
            'video': {
                'plot': video.description,
                'genre': ', '.join([g.name for g in video.genres if 'produksjon' not in g.name]),
                'aired': str(video.aired),
                'duration': video.duration,
                'mpaa': ', '.join([p[0:1].upper() for p in video.packages])
            }
        },
        'is_authorized': video.authorized,
        'is_playable': video.authorized,
        'is_folder': False,
        'context_menu': [
            ('Download', 'XBMC.RunPlugin(%s)' % (
                plugin.get_url(**{
                    'action': 'download', 
                    'api_params': {'video_id': video.id},
                    'video_id': video.id,
                    'video_full_name': video.full_name,
                    'duration': video.duration_ms,
                })
            ))
        ] if video.authorized else [],
        'url': plugin.get_url(action='play', api_params={'video_id': video.id}),
    } for video in sorted(videos, key=lambda v: v.episode_number, reverse=plugin.get_setting('reverse_sort'))]

    # Filter
    if plugin.get_setting('hide_unavailable_videos'):
        items = [i for i in items if i.get('is_authorized', True)]

    return items


# Action: Play
@plugin.action()
def play(params):
    ''' Play video '''
    # Get video playback details
    playable = dplay.playable(**params.api_params)

    if not playable:
        xbmcgui.Dialog().notification('Avspillingsfeil', 'Ikke autorisert')
        return None

    # Return first playable video URL
    streams = playable.streams

    if 'hls' in streams and streams['hls']:
        return streams['hls']

    xbmcgui.Dialog().notification('Avspillingsfeil', 'Ingen URL tilgjengelig')


# Action: Download
@plugin.action()
def download(params):
    # Check settings
    if not plugin.get_setting('download_path'):
        xbmcgui.Dialog().notification('Dplay Download', 'Nedlastningsmappe ikke definert')
        xbmcaddon.Addon(id=plugin.id).openSettings()
        return None

    # Get video playback details
    playable = dplay.playable(**params.api_params)

    if not playable:
        xbmcgui.Dialog().notification('Dplay Download', 'Ikke autorisert')
        return None

    stream = playable.streams.get('hls')
    
    if not stream:
        xbmcgui.Dialog().notification('Dplay Download', 'No stream available')

    # Execute download script
    xbmc.executebuiltin('XBMC.RunScript(%s,%s,%s,%s,%s,%s)' % (
        'special://home/addons/%s/lib/dplay_download.py' % (plugin.id),
        quote(stream),
        params.video_id,
        params.video_full_name,
        params.duration,
        plugin.get_setting('download_path')
    ))


# Action: Channels
@plugin.action()
def channels(params):
    ''' Display list of channels '''

    # Get channels
    channels = dplay.channels(**params.api_params)

    items = [{
        'label': '%s' % (channel.name),
        'thumb': channel.get_image_src('logo') or channel.get_image_src('default'),
        'fanart': channel.get_image_src('default'),
        'info': {
            'video': {
                'plot': channel.description,
            }
        },
        # 'is_authorized': show.authorized,
        'is_folder': True,
        'url': plugin.get_url(action='videos', api_params={
            'filter': {'primaryChannel.id': channel.id},
            'sort': ['-publishStart'],
        }),
    } for channel in channels]

    # Filter
    # if plugin.get_setting('hide_unavailable_shows'):
    #     items = [i for i in items if i.get('is_authorized', True)]

    return items



# Main
if __name__ == '__main__':
    plugin.run()  # Start plugin