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

# In[10]:


urls = ['https://xbrlus.github.io/cafr/samples/3/Alexandria-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/4/FallsChurch-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/5/Loudoun-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/6/ga-20190116.htm',
        'https://xbrlus.github.io/cafr/samples/1/StPete_StmtNetPos_iXBRL_20190116.htm',
        'https://xbrlus.github.io/cafr/samples/2/VABeach_StmtNetPos_iXBRL_20190116.htm',
        'https://xbrlus.github.io/cafr/samples/7/ut-20190117.htm']


# ## Libraries
# **BeautifulSoup**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

# In[11]:


import re

# In Python 3.7, dict is automatically ordered, but to allow for people using previous versions,
# need to use an OrderedDict or the results will be messy.
from collections import OrderedDict


# In[16]:


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

# In[17]:


class XbrliDocument:
    import requests

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


# In[67]:


class SummarySpreadsheet:
    from pandas import Series, DataFrame
    import pandas as pd
    import numpy as np
    
    def __init__(self, paths = [], urls = [], config_path = 'config.csv'):
        self.paths = paths
        self.urls = urls
        self.config_path = config_path
        self.docs = []
        self._dataframe = None       # The actual data parsed from the documents.
        self._output_fields = None   # Controlled by config.csv.
        
        # Load all specified documents.
        for path in paths:
            print(f'Loading {path}...')
            try:
                doc = XbrliDocument(path=path)
                self.docs.append(doc)
            except:
                pass

        for url in urls:
            print(f'Downloading {url}...')
            try:
                doc = XbrliDocument(url=url)
                self.docs.append(doc)
            except:
                pass

    def to_csv(self, path='output.csv'):
        self.dataframe.to_csv(path, index=False)

    def to_excel(self, path='output.xlsx'):
        # To have numbers not be treated as strings in the Excel file, have to specify the type of the column.
        # Easy approach is to just try turning each column into a numeric column and see if it works
        # (it will fail if any value is not a number).
        df = self.dataframe
        for col in df.columns:
            try:
                df[col] = self._to_numeric(df[col])
            except:
                pass
        df.to_excel(path, index=False)

    @property
    def dataframe(self):
        if self._dataframe is not None: return self._dataframe

        # Build up data dictionary to become DataFrame.
        sheet_data = {}
        
        # For each output field, go through each doc and get the value based on input fields
        for output_name, input_names in self.output_fields.items():
            values = []
            for doc in self.docs:
                for name in input_names:
                    value_found = False
                    if name in doc.ix_fields:
                        values.append(doc.ix_fields[name])
                        value_found = True
                        break
                    
                # If no value for this output field, need an empty value.
                if not value_found:
                    values.append('')
            sheet_data[output_name] = values
         
        self._dataframe = DataFrame(sheet_data)
        return self._dataframe

    @property
    def output_fields(self):
        ''' 
        If the config CSV file exists, it is used to determine what to output.
        If config file doesn't exist, uses all fields specified in the docs.

        CSV Format:

        Output Field Name,Input Field Name
        Document Title,cafr:DocumentTitle

        The same Output Field Name can be used multiple times, 
        to allow multiple Input Field Names tied to the same output name.
        In that case, only the first matching Input Field Name will be used for a document.

        Returns a dictionary with the output field name as the key and a list of input fields as the value.

        {'Document Title': ['cafr:DocumentTitle'],
         'Name of Government': ['cafr:NameOfGovernment']}
        '''
        if self._output_fields: return self._output_fields
        
        self._output_fields = OrderedDict()
        try:
            df = pd.read_csv(self.config_path)
            for output_name, input_name in df.itertuples(index=False):
                inputs = self._output_fields.setdefault(output_name, [])
                inputs.append(input_name)
        except FileNotFoundError:
            for doc in self.docs:
                for key in doc.ix_fields:
                    if key not in self._output_fields:
                        # The input names list in this case just uses the key name.
                        self._output_fields[key] = [key]
        return self._output_fields
    
    def _to_numeric(self, iterable, downcast='signed'):
        ''' Fixes up problems with converting strings to numbers, then uses pd.to_numeric() to do the conversion. 
        Raises exception if all values are not numeric. '''
        converted = []
        for index, item in enumerate(iterable):
            if isinstance(item, str):
                # Numeric conversions can't handle commas.
                item = item.replace(',', '')
                
                # Empty string will fail to convert, so turn it into NotANumber...
                if item == '': item = np.nan
            converted.append(item)
        return pd.to_numeric(converted, downcast=downcast)


# In[44]:


def main(paths=None):
    ''' For development, pass a list of paths and urls will be skipped. '''
    if paths:
        spreadsheet = SummarySpreadsheet(paths=paths)
    else:
        spreadsheet = SummarySpreadsheet(urls=urls)
        
    spreadsheet.to_csv()
    print('Generated output.csv.')
    
    spreadsheet.to_excel()
    print('Generated output.xlsx')


# In[19]:


def test():
    from mydir import mydir
    from pathlib import Path
    
    paths = [str(path) for path in Path('test_data').iterdir() if '.xhtml' in str(path) or '.htm' in str(path)]
    main(paths)


# In[70]:


#main()
test()

