'''
iXBRL is a library to support parsing inline XBRL documents.

Resources
- iXBRL spec: http://www.xbrl.org/specification/inlinexbrl-part1/rec-2013-11-18/inlinexbrl-part1-rec-2013-11-18.html
- [iXBRL schema](http://www.xbrl.org/specification/inlinexbrl-part2/rec-2013-11-18/inlinexbrl-part2-rec-2013-11-18.html)
- [iXBRL primer](http://www.xbrl.org/WGN/inlineXBRL-part0/WGN-2015-12-09/inlineXBRL-part0-WGN-2015-12-09.html)
- [XBRL - Wikipedia](https://en.wikipedia.org/wiki/XBRL)

Libraries
- BeautifulSoup: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
'''

import re
import requests
from bs4 import BeautifulSoup
import datetime


# ## iXBRL classes
# A class for most iXBRL elements.
# 
# Some are defined but not being used yet in the code, since some elements (like ``ix:hidden``) aren't important in the parsing process. Some are not defined yet (like ``xbrldi:explicitmember``) because we just mine their info from the HTML and don't need to instantiate them as objects.
# 
# At some point we may want to allow for writing out a pure XBRL document, in which case all elements will need an associated class that knows how to write itself out in XBRL.

# In[245]:


class Element:    
    def __init__(self, tag, doc):
        self.tag = tag
        self.doc = doc   # This should be a weakref, but that wasn't working w/property, need to investigate.
    
    @property
    def name(self):
        # This is the iXBRL name attribute, not the BeautifulSoup tag name...
        return self.tag['name']
    
    @property
    def string(self):
        return self.tag.string
    
    @property
    def contextref(self):
        return self.tag['contextref']
    
    @property
    def context(self):
        return self.doc.contexts[self.contextref]


# In[246]:


class IXHeader(Element):
    '''
    The ix:header element contains the non-displayed portions of the Target Document.
    
    The ix:header element MUST NOT be a descendant of an HTML head element.
    The ix:header element MUST have no more than one ix:hidden child element.
    The ix:header element MUST have no more than one ix:resources child element.

    <ix:header>
    Content: (ix:hidden? ix:references* ix:resources?)
    </ix:header>
    '''
    @property
    def contexts(self):
        contexts = []
        context_class = element_classes['xbrli:context']
        for tag in self.tag.find_all({'xbrli:context'}):
            contexts.append(context_class(tag, self.doc))
        return contexts


# In[247]:


class XBRLIContext(Element):
    '''
    The xbrli:context element MUST NOT have any descendant elements with a namespace name which has a 
    value of http://www.xbrl.org/2013/inlineXBRL.    
    '''
    @property
    def id(self):
        return self.tag['id']
    
    @property
    def explicit_members(self):
        try:
            return self._explicit_members
        except:
            # Using a set for fast searching.
            self._explicit_members = set()            
            for member in self.tag({'xbrldi:explicitmember'}):
                self.explicit_members.add(member.string)
        return self._explicit_members
    
    @property
    def period(self):
        ''' Returns a datetime.date object representing the period specified for this element, or 1900-01-01 to support sorting by date. '''
        # Doing this properly needs more review of the spec -- for now assuming zero or one xbrli:instant element.
        # <xbrli:period><xbrli:instant>2016-11-30</xbrli:instant></xbrli:period>
        try:
            return self._period
        except:
            # For now just returning the first instant we find.
            instances = self.tag({'xbrli:instant'})
            
            if instances and instances[0].string:
                self._period = datetime.date.fromisoformat(instances[0].string)
            else:
                self._period = datetime.date.fromisoformat('1900-01-01')
            return self._period


# In[248]:


class IXContinuation(Element):
    '''
    The ix:continuation element is used to define data that is to be treated as part of 
    ix:footnote or ix:nonNumeric elements.
    
    <ix:continuation continuedAt = NCName id = NCName>
    Content: ( any element | any text node )*
    </ix:continuation>
    '''
    pass


# In[249]:


class IXExclude(Element):
    '''
    The ix:exclude element is used to encapsulate data that is to be excluded from the processing of 
    ix:footnote or ix:nonNumeric elements.
    
    <ix:exclude>
    Content: ( any element | any text node )*
    </ix:exclude>
    '''
    pass


# In[250]:


class IXFootnote(Element):
    '''
    The ix:footnote element represents the link:footnote element.
    
    <ix:footnote
    any attribute with a namespace name which has the value http://www.w3.org/XML/1998/namespace

    footnoteRole = anyURI
    continuedAt = NCName
    id = NCName
    title = string>
    Content: ( any element | any text node ) +
    </ix:footnote>
    '''
    pass


# In[251]:


class IXFraction(Element):
    '''
    The ix:fraction element denotes an XBRL fact which is an element of type, or derived from type, fractionItemType.
    
    <ix:fraction
    any attribute with a namespace name which has a value other than http://www.xbrl.org/2013/inlineXBRL

    contextRef = NCName
    id = NCName
    name = QName
    order = decimal
    target = NCName
    tupleRef = NCName
    unitRef = NCName>
    Content: ( any text node | any children with a namespace name which has a value other than http://www.xbrl.org/2013/inlineXBRL | ix:fraction | ix:denominator | ix:numerator ) +
    </ix:fraction>
    '''
    pass


# In[252]:


class IXDenominator(Element):
    '''
    The ix:denominator element denotes an XBRL denominator element.
        
    <ix:denominator
    format = QName
    scale = integer
    sign = string>
    Content: ( non-empty text node )
    </ix:denominator>
    '''
    pass


# In[253]:


class IXNumerator(Element):
    '''
    The ix:numerator element denotes an XBRL numerator element.
    
    <ix:numerator
    format = QName
    scale = integer
    sign = string>
    Content: ( non-empty text node )
    </ix:numerator>
    '''
    pass


# In[254]:


class IXHidden(Element):
    '''
    The ix:hidden element is used to contain XBRL facts that are not to be displayed in the browser.
    
    <ix:hidden>
    Content: ( ix:footnote | ix:fraction | ix:nonFraction | ix:nonNumeric | ix:tuple) +
    </ix:hidden>
    '''
    pass


# In[255]:


class IXNonFraction(Element):
    '''
    The ix:nonFraction element denotes an XBRL numeric item which is an element which is not of type, 
    nor derived from type, fractionItemType.
    
    <ix:nonFraction
    any attribute with a namespace name which has a value other than http://www.xbrl.org/2013/inlineXBRL

    contextRef = NCName
    decimals = xbrli:decimalsType
    format = QName
    id = NCName
    name = QName
    order = decimal
    precision = xbrli:precisionType
    target = NCName
    tupleRef = NCName
    scale = integer
    sign = string
    unitRef = NCName>
    Content: ( ix:nonFraction | any text node )
    </ix:nonFraction>
    '''
    @property
    def scale(self):
        return int(self.tag['scale'])
    
    @property
    def sign(self):
        ''' Returns either 1 or -1, so the value can be multiplied by that amount. '''
        try:
            if self.tag['sign'] == '-':
                return -1
        except:
            pass
        return 1
    
    @property
    def string(self):
        # Optional scale attribute will be 0, 3 or 6, number needs to be multiplied by 10 ** scale.
        
        # Have to remove commas from the number (sigh).
        # A non-numeric value raises exception, we treat that case as a zero (often it's a dash character).
        try:
            number = int(self.tag.string.replace(',', '')) * self.sign
        except:
            return '0'
        
        try:
            # In an exception handler in case there is no scale.
            multiplier = 10 ** self.scale
            number *= multiplier
        except:
            pass
        return str(number)


# In[256]:


class IXNonNumeric(Element):
    '''
    The ix:nonNumeric element denotes an XBRL non-numeric item.
    
    <ix:nonNumeric
    any attribute with a namespace name which has a value other than http://www.xbrl.org/2013/inlineXBRL
    
    contextRef = NCName
    continuedAt = NCName
    escape = boolean
    format = QName
    id = NCName
    name = QName
    order = decimal
    target = NCName
    tupleRef = NCName>
    Content: ( any element | any text node ) *
    </ix:nonNumeric>
    '''
    pass


# In[257]:


class IXReferences(Element):
    '''
    The ix:references element is used to contain reference elements which are required by a given Target Document.
    
    <ix:references
    any attribute with a namespace name which has a value other than http://www.xbrl.org/2013/inlineXBRL
    
    id = NCNametarget = NCName
    target = NCName>
    Content: ( link:schemaRef | link:linkbaseRef) +
    </ix:references>
    '''
    pass


# In[258]:


class IXRelationship(Element):
    '''
    <ix:relationship
    any attribute with a namespace name which has the value http://www.w3.org/XML/1998/namespace
    
    arcrole = anyURI
    fromRefs = List of NCName values
    linkRole = anyURI
    order = decimal
    toRefs = List of NCName values
    </ix:relationship>
    '''
    pass


# In[259]:


class IXResources(Element):
    '''
    The ix:resources element is used to contain resource elements which are required by one or more Target Documents.
    
    <ix:resources>
    Content: ( ix:relationship | link:roleRef | link:arcroleRef | xbrli:context | xbrli:unit) *
    </ix:resources>
    '''
    pass


# In[260]:


class IXTuple(Element):
    '''
    The ix:tuple element denotes an XBRL tuple.
    
    <ix:tuple
    any attribute with a namespace name which has a value other than http://www.xbrl.org/2013/inlineXBRL
    
    id = NCName
    name = QName
    order = decimal
    target = NCName
    tupleID = NCName
    tupleRef = NCName>
    Content: ( any children with a namespace name which has a value other than http://www.xbrl.org/2013/inlineXBRL | ix:fraction | ix:nonFraction | ix:nonNumeric | ix:tuple | any text node ) *
    </ix:tuple>
    '''
    pass


# In[261]:


# Global that correlates tag names with the class representing that tag.
element_classes = {
    'ix:continuation': IXContinuation,
    'ix:exclude': IXExclude,
    'ix:footnote': IXFootnote,
    'ix:fraction': IXFraction,
    'ix:denominator': IXDenominator,
    'ix:numerator': IXNumerator,
    'ix:header': IXHeader,
    'ix:hidden': IXHidden,
    'ix:nonfraction': IXNonFraction,
    'ix:nonnumeric': IXNonNumeric,
    'ix:references': IXReferences,
    'ix:relationship': IXRelationship,
    'ix:resources': IXResources,
    'ix:tuple': IXTuple,
    'xbrli:context': XBRLIContext
}


# In[262]:

class Criterion:
    ''' Represents the requirements for a column in the spreadsheet.

        The name is the name attribute of the HTML element, such as:
        
            us-cafr:Liabilities
            
        The list of required members are the required context values, such as:
        
            us-cafr:GovernmentalActivitiesMember us-cafr:NetMember
    '''    
    def __init__(self, name, required_members = []):
        self.name = name
        self.required_members = required_members
    
    def __str__(self):
        return f"{self.name} ({' '.join(self.required_members)})"
    
    def __repr__(self):
        return self.__str__()
    
    def matches_element(self, element):
        try:
            if element.name != self.name:
                return False
        except:
            return False
        
        # Fails if no formal context definition was provided, in which case we just try to match the contextref attribute.
        try:
            context_members = element.context.explicit_members
        except:
            context_members = [element.tag['contextref']]
            
        for member in self.required_members:
            if member not in context_members:
                return False
        return True

class XbrliDocument:
    def __init__(self, path = None, url = None):
        if path:
            with open(path,'r', encoding='latin1') as source:
                try:
                    html = source.read()
                except Exception as e:
                    print(f'*** Error: Unable to read {path}: {e}')
                    raise e
        elif url:
            try:
                html = requests.get(url).text
            except Exception as e:
                print(f'*** Error: Unable to read {url}: {e}')
                raise e
        else:
            raise Exception("Need a path or url argument!")
        
        self.path = path

        soup = BeautifulSoup(html, 'lxml')
        self.ix_elements = [element_classes[tag.name](tag, self) for tag in soup.find_all({re.compile(r'^ix:')})]
                
    @property
    def header(self):
        ''' The header element for the document. '''
        # Not going to be referenced much so no need to store as an instance variable, just look it up.
        for element in self.ix_elements:
            if isinstance(element, IXHeader):
                return element
        
    @property
    def contexts(self):
        # Contexts will be accessed frequently, so storing them.
        try:
            return self._contexts
        except:
            self._contexts = {}   # context id: element
            for context in self.header.contexts:
                self._contexts[context.id] = context
        return self._contexts
