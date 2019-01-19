#!/usr/bin/env python
# coding: utf-8

# ## Urls to parse
# URLs that take too long to return data:
# - https://xbrlus.github.io/cafr/samples/8/va-c-bris-20160630.xhtml

# urls = ['https://xbrlus.github.io/cafr/samples/10/va-o-albe-20170630.xhtml',
#         'https://xbrlus.github.io/cafr/samples/9/va-t-ashl-20170630.xhtml', 
#         'https://xbrlus.github.io/cafr/samples/8/va-c-bris-20160630.xhtml',
#         'https://xbrlus.github.io/cafr/samples/6/ga-20190116.htm',
#         'https://xbrlus.github.io/cafr/samples/1/StPete_StmtNetPos_iXBRL_20190116.htm',
#         'https://xbrlus.github.io/cafr/samples/2/VABeach_StmtNetPos_iXBRL_20190116.htm',
#         'https://xbrlus.github.io/cafr/samples/7/ut-20190117.htm']

# In[31]:


urls = ['https://xbrlus.github.io/cafr/samples/3/Alexandria-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/4/FallsChurch-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/5/Loudoun-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/6/ga-20190116.htm',
        'https://xbrlus.github.io/cafr/samples/7/ut-20190117.htm']


# ## Libraries
# **BeautifulSoup**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

import requests
from pandas import Series, DataFrame
import pandas as pd
import re


def config_fields(path = 'config.csv'):
    ''' 
    If the config CSV file exists, it is used to determine what to output.
    If config file doesn't exist, raises exception.
    
    CSV Format:
    
    Output Field Name,Input Field Names (a;b;c)
    Document Title,cafr:DocumentTitle
    
    Returns a dictionary with the output field name as the key and a list of input fields as the value.
    
    {'Document Title': ['cafr:DocumentTitle'],
     'Name of Government': ['cafr:NameOfGovernment']}
    '''
    df = pd.read_csv(path)
    return {row[0] : row[1].split(';') for row in df.itertuples(index=False)}

def configure_data(data, fields):
    ''' Given a dictionary of data and a dictionary of configuration info, returns dictionary conforming to the configuration. '''
    configured = {}

    # Determine how many entries each column must have, for missing fields.
    #row_count = len(data.values[0])
    
    # TODO: Support multiple input fields -- need more info on what should happen.
    for name, input_fields in fields.items():
        for field in input_fields:
            if field in data:
                configured[name] = data[field]
    return configured


# This is a quick hack replacement for BeautifulSoup, to work around whatever problem we're having there.
def tags_from_html(name, html):
    tags = []
    results = re.findall(f'(<\s*{name}.*?>(.*?)<\s*/\s*{name}>)', html, flags = re.DOTALL | re.MULTILINE)
    
    for element, content in results:
        tag = {'name': name}
        tag['content'] = content
        
        atts = {}
        att_results = re.findall(f'(\S+)=["\']?((?:.(?!["\']?\s+(?:\S+)=|[>"\']))+.)["\']?', element)
        for att, value in att_results:
            atts[att.lower()] = value   # Lower-casing attribute name to avoid case errors in the HTML.
        tag['attributes'] = atts
        tags.append(tag)
    return tags

class XbrliDocument:
    def __init__(self, path = None, url = None):
        if path:
            with open(path,'r') as source:
                html = source.read()
        elif url:
            html = requests.get(url).text
            print(f'DEBUG: Got html from {url}')
        else:
            raise Exception("Need a path or url argument!")
        
        self.contexts = self._contexts_from_html(html)
        self.ix_fields = self._ix_fields_from_html(html)
    
    def _contexts_from_html(self, html):
        contexts = {}   # id: text description
        for tag in tags_from_html('xbrli:context', html):
            text = ''
            members = []
            for member in tags_from_html('xbrldi:explicitMember', tag['content']):
                try:
                    #members.append(member['content'].replace('cafr:', '').replace('Member', ''))
                    members.append(member['content'])
                    members.sort()
                except:
                    pass
            text += ' '.join(members)    
            contexts[tag['attributes']['id']] = text 
        return contexts
    
    def _ix_fields_from_html(self, html):
        ix_fields = {}   # name (context description): [text]
        for ix_name in ('ix:nonNumeric', 'ix:nonFraction'):
            for tag in tags_from_html(ix_name, html):
                try:
                    context = tag['attributes']['contextref']
                    description = self.contexts[context]

                    # If there is description text, put it in parenthesis (if empty string, no parenthesis).
                    if description: description = f' ({description})'

#                    name = tag['attributes']['name'].replace('cafr:', '')
                    name = tag['attributes']['name']
                    text = tag['content']

                    ix_fields[f'{name}{description}'] = text 
                except Exception as e:
                    print(f"*** Exception: {type(e)}: {e}")
        return ix_fields


def main(paths=None):
    ''' For development, pass a list of paths and urls will be skipped. '''
    fields = {}
    try:
        fields = config_fields()
        print(f'Config file (config.csv) found.')
    except:
        print(f'Config file (config.csv) not found, will output all fields as found in documents.')

    data = {}
    docs = []
    
    if paths:
        for path in paths:
            print(f'Loading {path}...')
            doc = XbrliDocument(path=path)
            docs.append(doc)  
    else:
        for url in urls:
            print(f'Downloading {url}...')
            doc = XbrliDocument(url=url)
            docs.append(doc)

    # Because docs can have missing fields, and for the spreadsheet all docs must have entries for all fields,
    # first need to figure out what all the fields from all the docs are, before processing the data.
    for doc in docs:
        for key in doc.ix_fields:
            data.setdefault(key, [])

    # Now can process the docs.
    for doc in docs:
        for key, value in doc.ix_fields.items():
            data_list = data.setdefault(key, [])
            data_list.append(value)

        # And finally add blank entries for any missing fields.
        for key, value in data.items():
            if key not in doc.ix_fields:
                value.append('')
    
    if fields:
        data = configure_data(data, fields)

    # Use Pandas to turn data dictionary into Excel
    df = pd.DataFrame(data=data, dtype=int)
    xlWriter = pd.ExcelWriter('output.xlsx', engine='xlsxwriter',options={'strings_to_numbers': True})
    df.to_excel(xlWriter, index=False, sheet_name='CAFR Data')

    print(f"Processed data for {len(urls)} entities, with a total of {len(data)} fields. See output.xlsx.")

# In[34]:


def test():
    from mydir import mydir
    from pathlib import Path
    
    paths = [str(path) for path in Path('test_data').iterdir()]
    main()
    #main(paths)
	
#main()
test()