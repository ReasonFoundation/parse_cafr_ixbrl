#!/usr/bin/env python
# coding: utf-8

# # Get data from websites
# https://davidtauriello.github.io/cafr/ixviewer/../samples/3/Alexandria-2018-Statements.htm
#  
# https://davidtauriello.github.io/cafr/ixviewer/ix?doc=../samples/4/FallsChurch-2018-Statements.htm
#  
# https://davidtauriello.github.io/cafr/ixviewer/ix?doc=../samples/5/Loudoun-2018-Statements.htm

# ## Files to parse
# (Later we can do URLs also)

# In[95]:


file_paths = ['Alexandria-2018-Statements.htm', 'FallsChurch-2018-Statements.htm', 'Loudoun-2018-Statements.htm']


# ## Libraries
# **BeautifulSoup**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

# In[1]:


#from bs4 import BeautifulSoup
import re
import pandas as pd
#soup = BeautifulSoup(ixbrl, 'html.parser')


# In[8]:


# This is my little function for inspecting objects.
from mydir import mydir


# In[59]:


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
        
#tags_from_html('xbrldi:explicitMember', test_html)
#tags_from_html('xb', test_html)


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

# In[73]:


class XbrliDocument:
    def __init__(self, path = None, url = None):
        # TODO: Add url support.
        if path:
            with open(path,'r') as source:
                html = source.read()
        
        self.contexts = self._contexts_from_html(html)
        self.ix_fields = self._ix_fields_from_html(html)
    
    def _contexts_from_html(self, html):
        contexts = {}   # id: text description
        for tag in tags_from_html('xbrli:context', html):
            text = ''
            #content = tag['content']
            members = []
            for member in tags_from_html('xbrldi:explicitMember', tag['content']):
                try:
                    members.append(member['content'][5:])
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

                    name = tag['attributes']['name'][5:]
                    text = tag['content']

                    ix_fields[f'{name}{description}'] = text 
                except Exception as e:
                    print(f"*** Exception: {e}")
        return ix_fields


# In[111]:


data = {}
docs = [XbrliDocument(path) for path in file_paths]

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
df.to_csv('output.csv', index=False)

print(f"Processed data for {len(file_paths)} entities, with a total of {len(data)} fields. See output.csv")

