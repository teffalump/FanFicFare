# -*- coding: utf-8 -*-

# Copyright 2012 Fanficdownloader team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Software: eFiction
import time
import logging
logger = logging.getLogger(__name__)
import re
import urllib2

from .. import BeautifulSoup as bs
from ..htmlcleanup import stripHTML
from .. import exceptions as exceptions

from base_adapter import BaseSiteAdapter,  makeDate

def getClass():
    return HPFanficArchiveComAdapter

# Class name has to be unique.  Our convention is camel case the
# sitename with Adapter at the end.  www is skipped.
class HPFanficArchiveComAdapter(BaseSiteAdapter):

    def __init__(self, config, url):
        BaseSiteAdapter.__init__(self, config, url)

        self.decode = ["Windows-1252",
                       "utf8"] # 1252 is a superset of iso-8859-1.
                               # Most sites that claim to be
                               # iso-8859-1 (and some that claim to be
                               # utf8) are really windows-1252.
        self.username = "NoneGiven" # if left empty, site doesn't return any message at all.
        self.password = ""
        self.is_adult=False
        
        # get storyId from url--url validation guarantees query is only sid=1234
        self.story.setMetadata('storyId',self.parsedUrl.query.split('=',)[1])
        
        
        # normalized story URL.
        self._setURL('http://' + self.getSiteDomain() + '/stories/viewstory.php?sid='+self.story.getMetadata('storyId'))
        
        # Each adapter needs to have a unique site abbreviation.
        self.story.setMetadata('siteabbrev','hpffa')

        # The date format will vary from site to site.
        # http://docs.python.org/library/datetime.html#strftime-strptime-behavior
        self.dateformat = "%B %d, %Y"
            
    @staticmethod # must be @staticmethod, don't remove it.
    def getSiteDomain():
        # The site domain.  Does have www here, if it uses it.
        return 'www.hpfanficarchive.com'

    @classmethod
    def getSiteExampleURLs(cls):
        return "http://"+self.getSiteDomain()+"/stories/viewstory.php?sid=1234"

    def getSiteURLPattern(self):
        return re.escape("http://"+self.getSiteDomain()+"/stories/viewstory.php?sid=")+r"\d+$"

    ## Getting the chapter list and the meta data, plus 'is adult' checking.
    def extractChapterUrlsAndMetadata(self):

        # index=1 makes sure we see the story chapter index.  Some
        # sites skip that for one-chapter stories.
        url = self.url
        logger.debug("URL: "+url)

        try:
            data = self._fetchUrl(url)
        except urllib2.HTTPError, e:
            if e.code == 404:
                raise exceptions.StoryDoesNotExist(self.url)
            else:
                raise e

            
        if "Access denied. This story has not been validated by the adminstrators of this site." in data:
            raise exceptions.FailedToDownload(self.getSiteDomain() +" says: Access denied. This story has not been validated by the adminstrators of this site.")
            
        # use BeautifulSoup HTML parser to make everything easier to find.
        soup = bs.BeautifulSoup(data)
        # print data

        # Now go hunting for all the meta data and the chapter list.
        
        ## Title
        a = soup.find('a', href=re.compile(r'viewstory.php\?sid='+self.story.getMetadata('storyId')+"$"))
        self.story.setMetadata('title',stripHTML(a))
        
        # Find authorid and URL from... author url.
        a = soup.find('a', href=re.compile(r"viewuser.php\?uid=\d+"))
        self.story.setMetadata('authorId',a['href'].split('=')[1])
        self.story.setMetadata('authorUrl','http://'+self.host+'/stories/'+a['href'])
        self.story.setMetadata('author',a.string)

        # Find the chapters:
        for chapter in soup.findAll('a', href=re.compile(r'viewstory.php\?sid='+self.story.getMetadata('storyId')+"&chapter=\d+$")):
            # just in case there's tags, like <i> in chapter titles.
            self.chapterUrls.append((stripHTML(chapter),'http://'+self.host+'/stories/'+chapter['href']))

        self.story.setMetadata('numChapters',len(self.chapterUrls))

        # eFiction sites don't help us out a lot with their meta data
        # formating, so it's a little ugly.

        # utility method
        def defaultGetattr(d,k):
            try:
                return d[k]
            except:
                return ""

        # <span class="label">Rated:</span> NC-17<br /> etc
        labels = soup.findAll('span',{'class':'label'})
        for labelspan in labels:
            val = labelspan.nextSibling
            value = unicode('')
            while val and not defaultGetattr(val,'class') == 'label':
                value += unicode(val)
                val = val.nextSibling
            label = labelspan.string
            #print("label:%s\nvalue:%s"%(label,value))

            if 'Summary' in label:
                self.setDescription(url,value)

            if 'Rated' in label:
                self.story.setMetadata('rating', stripHTML(value))

            if 'Word count' in label:
                self.story.setMetadata('numWords', stripHTML(value))

            if 'Categories' in label:
                cats = labelspan.parent.findAll('a',href=re.compile(r'browse.php\?type=categories'))
                for cat in cats:
                    self.story.addToList('category',cat.string)

            if 'Characters' in label:
                chars = labelspan.parent.findAll('a',href=re.compile(r'browse.php\?type=characters'))
                for char in chars:
                    self.story.addToList('characters',char.string)

            if 'Genre' in label:
                genres = labelspan.parent.findAll('a',href=re.compile(r'browse.php\?type=class&type_id=1')) # XXX
                for genre in genres:
                    self.story.addToList('genre',genre.string)

            if 'Pairing' in label:
                ships = labelspan.parent.findAll('a',href=re.compile(r'browse.php\?type=class&type_id=4'))
                for ship in ships:
                    self.story.addToList('ships',ship.string)

            if 'Warnings' in label:
                warnings = labelspan.parent.findAll('a',href=re.compile(r'browse.php\?type=class&type_id=2')) # XXX
                for warning in warnings:
                    self.story.addToList('warnings',warning.string)

            if 'Completed' in label:
                if 'Yes' in stripHTML(value):
                    self.story.setMetadata('status', 'Completed')
                else:
                    self.story.setMetadata('status', 'In-Progress')

            if 'Published' in label:
                self.story.setMetadata('datePublished', makeDate(stripHTML(value), self.dateformat))
            
            if 'Updated' in label:
                self.story.setMetadata('dateUpdated', makeDate(stripHTML(value), self.dateformat))

        try:
            # Find Series name from series URL.
            a = soup.find('a', href=re.compile(r"viewseries.php\?seriesid=\d+"))
            series_name = a.string
            series_url = 'http://'+self.host+'/stories/'+a['href']

            # use BeautifulSoup HTML parser to make everything easier to find.
            seriessoup = bs.BeautifulSoup(self._fetchUrl(series_url))
            # can't use ^viewstory...$ in case of higher rated stories with javascript href.
            storyas = seriessoup.findAll('a', href=re.compile(r'viewstory.php\?sid=\d+'))
            i=1
            for a in storyas:
                # skip 'report this' and 'TOC' links
                if 'contact.php' not in a['href'] and 'index' not in a['href']:
                    if a['href'] == ('viewstory.php?sid='+self.story.getMetadata('storyId')):
                        self.setSeries(series_name, i)
                        self.story.setMetadata('seriesUrl',series_url)
                        break
                    i+=1
            
        except:
            # I find it hard to care if the series parsing fails
            pass
            
    # grab the text for an individual chapter.
    def getChapterText(self, url):

        logger.debug('Getting chapter text from: %s' % url)
        

        soup = bs.BeautifulSoup(self._fetchUrl(url),
                                     selfClosingTags=('br','hr')) # otherwise soup eats the br/hr tags.
        
        div = soup.find('div', {'id' : 'story'})

        if None == div:
            raise exceptions.FailedToDownload("Error downloading Chapter: %s!  Missing required element!" % url)
    
        return self.utf8FromSoup(url,div)
