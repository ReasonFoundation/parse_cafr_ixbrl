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
        'https://xbrlus.github.io/cafr/samples/1/StPete_StmtNetPos_iXBRL_20190116.htm',
        'https://xbrlus.github.io/cafr/samples/2/VABeach_StmtNetPos_iXBRL_20190116.htm',
        'https://xbrlus.github.io/cafr/samples/7/ut-20190117.htm']


# ## Libraries
# **BeautifulSoup**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

# In[2]:


import requests
import pandas as pd

import re


# In[3]:


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

# In[33]:


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
                    members.append(member['content'].replace('cafr:', '').replace('Member', ''))
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

                    name = tag['attributes']['name'].replace('cafr:', '')
                    text = tag['content']

                    ix_fields[f'{name}{description}'] = text 
                except Exception as e:
                    print(f"*** Exception: {type(e)}: {e}")
        return ix_fields


# In[34]:


data = {}
docs = []
for url in urls:
    print(f'Downloading {url}...')
    doc = XbrliDocument(url=url)
    docs.append(doc)

print(f"DEBUG: Found {len(docs)} docs")

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

# Use Pandas to turn data dictionary into csv.
df = pd.DataFrame(data)
#df.to_csv('output.csv', index=False)
df.to_excel('output.xlsx', index=False)

print(f"Processed data for {len(urls)} entities, with a total of {len(data)} fields. See output.xlsx.")

