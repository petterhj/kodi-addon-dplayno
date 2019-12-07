#!/usr/bin/python
# -*- coding: utf-8 -*-

# Imports
import arrow
import logging


# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('[Dplay.%s]' % (__name__))


# Constants
TIMEZONE = None



# Class: Element
class Element(object):
    # Init
    def __init__(self, data, included=[]):
        # Element
        self.id = data.get('id')
        self.type = data.get('type')

        self.attributes = data.get('attributes')
        self.relationships = data.get('relationships')
        self.included = included


    # Get related
    def _get_related(self, relation):
        if not self.relationships:
            return []

        logger.info('Getting related %s for %s (%s)' % (relation, self.id, self.type))

        # Relationship
        relationship = self.relationships.get(relation)

        # Check if relation exists
        if not relationship or 'data' not in relationship:
            logger.warning('Relationship not found')
            return []

        # Determine if single relation
        is_single_relation = False if type(relationship.get('data')) == list else True

        # Find relation ID(s)
        related_ids = []
        
        if is_single_relation:
            related_ids = [relationship.get('data', {}).get('id')]
        else:
            related_ids = [r.get('id') for r in relationship.get('data', [])]

        # Return related element(s)
        related_type = relation if is_single_relation else relation[0:-1] # Sketchy...
        related_elements = []

        logger.info('Finding %d related element(s) of type "%s"' % (len(related_ids), related_type))
        
        for element in self.included:
            if element.get('type') == related_type and element.get('id') in related_ids:
                related_elements.append(element)

        return related_elements[0] if is_single_relation and len(related_elements) > 0 else related_elements


    # Dictionary representation
    def dict(self):
        d = self.__dict__
        del d['attributes']
        del d['relationships']
        del d['included']
        return d


    # Representation
    def __repr__(self):
        return '<%s: id=%s, name=%s>' % (
            self.type.capitalize(), self.id, repr(self.__dict__.get('name'))
        )


# Class: User
class User(Element):
    # Init
    def __init__(self, data, included=[]):
        # Super
        super(User, self).__init__(data, included)

        # Attributes
        self.profile_id = self.attributes.get('selectedProfileId')
        self.realm = self.attributes.get('realm')
        self.packages = [p.lower() for p in self.attributes.get('packages')]
        self.is_anonymous = self.attributes.get('anonymous')


    # Representation
    def __repr__(self):
        return '<%s: id=%s, packages=%s>' % (
            self.type.capitalize(), self.id, ','.join(self.packages)
        )


# Class: Genre
class Genre(Element):
    # Init
    def __init__(self, data, included=[]):
        # Super
        super(Genre, self).__init__(data, included)

        # Attributes
        self.name = self.attributes.get('name')


# Class: Image
class Image(Element):
    # Init
    def __init__(self, data, included=[]):
        # Super
        super(Image, self).__init__(data, included)

        # Attributes
        self.kind = self.attributes.get('kind')
        self.src = self.attributes.get('src')
        self.width = self.attributes.get('width')
        self.height = self.attributes.get('height')


    # Representation
    def __repr__(self):
        return '<%s: id=%s, kind=%s>' % (
            self.type.capitalize(), self.id, self.kind
        )


# Class: Season
class Season(Element):
    # Init
    def __init__(self, data, included=[]):
        # Super
        super(Season, self).__init__(data, included)

        # Attributes
        self.season_number = self.attributes.get('seasonNumber')
        self.episode_count = self.attributes.get('episodeCount')
        self.video_count = self.attributes.get('videoCount')


# Class: Program
class Program(Element):
    # Init
    def __init__(self, data, included=[], user=None):
        # Super
        super(Program, self).__init__(data, included)

        # Attributes
        self.name = self.attributes.get('name').encode('utf-8')
        self.alternate_id = self.attributes.get('alternateId')
        self.description = self.attributes.get('description')
        self.packages = [p.get('id').lower() for p in self.relationships.get('contentPackages', {}).get('data', [])]
        self.authorized = user != None and len(set(user.packages).intersection(self.packages)) > 0
        
        # Related
        self.images = [Image(i) for i in self._get_related('images')]
        self.genres = [Genre(g) for g in self._get_related('genres')]


    # Get image source by kind
    def get_image_src(self, kind):
        for image in self.images:
            if image.kind == kind:
                return image.src
        return None


# Class: Show
class Show(Program):
    # Init
    def __init__(self, data, included=[], user=None):
        # Super
        super(Show, self).__init__(data, included, user)

        # Attributes
        self.season_numbers = self.attributes.get('seasonNumbers', [])
        self.season_count = len(self.season_numbers)
        self.episode_count = self.attributes.get('episodeCount')
        self.video_count = self.attributes.get('videoCount')
        self.newest_episode_publish_start = arrow.get(self.attributes.get('newestEpisodePublishStart')).to(TIMEZONE)

        # Related
        self.seasons = [Season(s) for s in self._get_related('seasons')]


# Class: Video
class Video(Program):
    # Init
    def __init__(self, data, included=[], user=None):
        # Super
        super(Video, self).__init__(data, included, user)
        
        # Attributes
        self.season_number = self.attributes.get('seasonNumber')
        self.episode_number = self.attributes.get('episodeNumber')
        self.aired = arrow.get(self.attributes.get('airDate')).to(TIMEZONE)
        self.duration = (int(self.attributes.get('videoDuration', 0)) / 1000) # In seconds
        self.duration_ms = self.attributes.get('videoDuration', 0)

        self.availability = {}

        for available in self.attributes.get('availabilityWindows', []):
            package = available.get('package').lower()
            start = arrow.get(available.get('playableStart')).to(TIMEZONE) if available.get('playableStart') else None
            end = arrow.get(available.get('playableEnd')).to(TIMEZONE) if available.get('playableEnd') else None
            current_time = arrow.now(TIMEZONE)
            available_now = (current_time > start and not end) or (current_time > start and current_time < end)
            self.availability[package] = {
                'start': start,
                'end': end,
                'now': available_now,
            }

        # Description
        self.description += '\n\n'
        self.description += 'Aired: %s\n' % (
            self.aired.format('DD.MM.YYYY, HH:mm') if self.aired else '',
        )

        for package, availability in self.availability.items():
            start = availability['start']
            end = availability['end']
            self.description += '%s: %s - %s\n' % (
                package.capitalize(), 
                start.format('DD.MM.YYYY, HH:mm') if start else '',
                end.format('DD.MM.YYYY, HH:mm') if end else ''
            )
        
        # Authorization
        self.authorized = False

        for package in user.packages:
            if self.availability.get(package, {}).get('now', False):
                self.authorized = True

        # Related
        self.show = Show(self._get_related('show'))

        self.full_name = '%s (%s.%s): %s' % (
            self.show.name,
            str(self.season_number),#.zfill(2),
            str(self.episode_number),#.zfill(2),
            self.name,
        )



    # Representation
    def __repr__(self):
        return '<%s: id=%s, name=%s, aired=%s>' % (
            self.type.capitalize(), self.id, self.name, self.aired
        )


# Class: Playable
class Playable(Element):
    # Init
    def __init__(self, data, included=[]):
        # Super
        super(Playable, self).__init__(data, included)

        # Attributes
        self.streams = {
            p: s.get('url') for p, s in self.attributes.get('streaming', {}).iteritems()
        }


# Class: Channel
class Channel(Program):
    # Init
    def __init__(self, data, included=[], user=None):
        # Super
        super(Channel, self).__init__(data, included, user)

        # Attributes
        self.has_live_stream = self.attributes.get('hasLiveStream')