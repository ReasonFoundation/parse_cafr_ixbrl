#!/usr/bin/env python
# coding: utf-8

# ## Urls to parse
# URLs that take too long to return data:
# - https://xbrlus.github.io/cafr/samples/8/va-c-bris-20160630.xhtml

#     urls = ['https://xbrlus.github.io/cafr/samples/10/va-o-albe-20170630.xhtml',
#             'https://xbrlus.github.io/cafr/samples/9/va-t-ashl-20170630.xhtml', 
#             'https://xbrlus.github.io/cafr/samples/8/va-c-bris-20160630.xhtml',
#             'https://xbrlus.github.io/cafr/samples/6/ga-20190116.htm',
#             'https://xbrlus.github.io/cafr/samples/1/StPete_StmtNetPos_iXBRL_20190116.htm',
#             'https://xbrlus.github.io/cafr/samples/2/VABeach_StmtNetPos_iXBRL_20190116.htm',
#             'https://xbrlus.github.io/cafr/samples/7/ut-20190117.htm']

# In[18]:


urls = ['https://xbrlus.github.io/cafr/samples/3/Alexandria-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/4/FallsChurch-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/5/Loudoun-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/6/ga-20190116.htm',
        'https://xbrlus.github.io/cafr/samples/1/StPete_StmtNetPos_iXBRL_20190116.htm',
        'https://xbrlus.github.io/cafr/samples/2/VABeach_StmtNetPos_iXBRL_20190116.htm',
        'https://xbrlus.github.io/cafr/samples/7/ut-20190117.htm']


# ## Libraries
# **BeautifulSoup**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

# In[19]:


import requests
from pandas import Series, DataFrame
import pandas as pd
import re

# In Python 3.7, dict is automatically ordered, but to allow for people using previous versions,
# need to use an OrderedDict or the results will be messy.
from collections import OrderedDict


# In[20]:


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
    fields = OrderedDict()
    for row in df.itertuples(index=False):
        fields[row[0]] = row[1].split(';')
    return fields


# In[21]:


def configure_data(data, fields):
    ''' Given a dictionary of data and a dictionary of configuration info, returns dictionary conforming to the configuration. '''
    configured = OrderedDict()

    # Determine how many entries each column must have, for missing fields.
    #row_count = len(data.values[0])
    
    # TODO: Support multiple input fields -- need more info on what should happen.
    for name, input_fields in fields.items():
        for field in input_fields:
            if field in data:
                configured[name] = data[field]
    return configured


# In[22]:


# This is a quick hack replacement for BeautifulSoup, to work around whatever problem we're having there.
def tags_from_html(name, html):
    tags = []
    results = re.findall(f'(<\s*{name}.*?>(.*?)<\s*/\s*{name}>)', html, flags = re.DOTALL | re.MULTILINE)
    
    for element, content in results:
        tag = {'name': name}
        tag['content'] = content
        
        atts = OrderedDict()
        att_results = re.findall(f'(\S+)=["\']?((?:.(?!["\']?\s+(?:\S+)=|[>"\']))+.)["\']?', element)
        for att, value in att_results:
            atts[att.lower()] = value   # Lower-casing attribute name to avoid case errors in the HTML.
        tag['attributes'] = atts
        tags.append(tag)
    return tags


# ## Context definitions
# Need to get a description for each context. A context element looks like this:
# 
#        <xbrli:context id="_ctx9">
#           <xbrli:entity><xbrli:identifier scheme="http://www.govwiki.info">47210100100000</xbrli:identifier></xbrli:entity>
#           <xbrli:period><xbrli:instant>2018-06-30</xbrli:instant></xbrli:period>
#           <xbrli:scenario>
#              <xbrldi:explicitMember dimension="cafr:FinancialReportingEntityAxis">cafr:PrimaryGovernmentActivitiesMember</xbrldi:explicitMember>
#              <xbrldi:explicitMember dimension="cafr:BasisOfAccountingAxis">cafr:ModifiedAccrualBasisOfAccountingMember</xbrldi:explicitMember>
#              <xbrldi:explicitMember dimension="cafr:ActivityTypeAxis">cafr:GovernmentalTypeActivityMember</xbrldi:explicitMember>
#              <xbrldi:explicitMember dimension="cafr:ClassificationOfFundTypeAxis">cafr:GeneralFundMember</xbrldi:explicitMember>
#              <xbrldi:explicitMember dimension="cafr:MagnitudeAxis">cafr:MajorMember</xbrldi:explicitMember>
#           </xbrli:scenario>
#        </xbrli:context>
# 

# ## Actual data
# Data looks like this:
# 
#         <td id="_NETPOSITION_B10" style="text-align:right;width:114px;">$&#160;&#160;&#160;&#160;&#160;&#160;&#160;<ix:nonFraction name="cafr:CashAndCashEquivalents" contextRef="_ctx3" id="NETPOSITION_B10" unitRef="ISO4217_USD" decimals = "0" format="ixt:numdotdecimal">336,089,928</ix:nonFraction>&#160;</td>

# In[23]:


class XbrliDocument:
    def __init__(self, path = None, url = None):
        if path:
            with open(path,'r') as source:
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
        
        self.contexts = self._contexts_from_html(html)
        self.ix_fields = self._ix_fields_from_html(html)
    
    def _contexts_from_html(self, html):
        contexts = OrderedDict()   # id: text description
        for tag in tags_from_html('xbrli:context', html):
            text = ''
            members = []
            for member in tags_from_html('xbrldi:explicitMember', tag['content']):
                try:
                    members.append(member['content'])
                    members.sort()
                except:
                    pass
            text += ' '.join(members)    
            contexts[tag['attributes']['id']] = text 
        return contexts
    
    def _ix_fields_from_html(self, html):
        ix_fields = OrderedDict()   # name (context description): [text]
        for ix_name in ('ix:nonNumeric', 'ix:nonFraction'):
            for tag in tags_from_html(ix_name, html):
                try:
                    context = tag['attributes']['contextref']
                    
                    try:
                        description = self.contexts[context]
                    except:
                        description = context
                        print(f'*** Error: document missing context info for {context}, using context name instead.')

                    # If there is description text, put it in parenthesis (if empty string, no parenthesis).
                    if description: description = f' ({description})'

                    name = tag['attributes']['name']
                    text = tag['content']

                    ix_fields[f'{name}{description}'] = text 
                except Exception as e:
                    print(f"*** Exception: {type(e)}: {e}")
                    print(tag)
        return ix_fields


# In[24]:


def main(paths=None):
    ''' For development, pass a list of paths and urls will be skipped. '''
    fields = OrderedDict()
    try:
        fields = config_fields()
        print(f'Config file (config.csv) found.')
    except:
        print(f'Config file (config.csv) not found, will output all fields as found in documents.')

    data = OrderedDict()
    docs = []
    
    if paths:
        for path in paths:
            print(f'Loading {path}...')
            try:
                doc = XbrliDocument(path=path)
                docs.append(doc)
            except:
                pass
    else:
        for url in urls:
            print(f'Downloading {url}...')
            try:
                doc = XbrliDocument(url=url)
                docs.append(doc)
            except:
                pass

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

    # Use Pandas to turn data dictionary into csv.
    df = pd.DataFrame(data)
    
    # NOW: Have to pull commas out of numbers to convert them (sigh). Good Series practice!
    # NOW: A workaround is to go back to writing out csv, then things get properly read in as numbers.
    # TODO: Hack to get numeric data saved as numbers rather than strings.
    # TODO: Probably want the config file to specify the column format, then need to handle non-conforming data
    #for col in df.columns[3:]:                  # UPDATE ONLY NUMERIC COLS 
        #df.loc[df[col] == '-', col] = np.nan    # REPLACE HYPHEN WITH NaNs
        #df[col] = df[col].astype(int)         # CONVERT TO INT (handle float later?)   

    df.to_excel('output.xlsx', index=False)

    print(f"Processed data for {len(docs)} entities, wrote out {len(data)} fields. See output.xlsx.")


# In[25]:


def test():
    from mydir import mydir
    from pathlib import Path
    
    paths = [str(path) for path in Path('test_data').iterdir() if '.htm' in str(path)]
    main(paths)


# In[26]:


#main()
test()

