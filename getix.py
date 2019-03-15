#!/usr/bin/env python
# coding: utf-8

# # getix
# This script is an in-progress effort to make it easy to parse iXBRL files and generate spreadsheet output (Excel and CSV).
# 
# It's currently a proof of concept, and the Excel output assumes the tags currently listed in config.csv. The CSV output is more resilient. The next step is making the script more robust and flexible.
# 
# The ``getix.ipynb`` file is considered the source (it's a [Jupyter Notebook](https://jupyter.org)), and ``getix.py`` is derived from that. You can run the script using either file, though for the .ipynb file you need to install Jupyter and run the ``jupyter notebook`` command.

# ## Resources
# - [iXBRL spec](http://www.xbrl.org/specification/inlinexbrl-part1/rec-2013-11-18/inlinexbrl-part1-rec-2013-11-18.html)
# - [iXBRL schema](http://www.xbrl.org/specification/inlinexbrl-part2/rec-2013-11-18/inlinexbrl-part2-rec-2013-11-18.html)
# - [iXBRL primer](http://www.xbrl.org/WGN/inlineXBRL-part0/WGN-2015-12-09/inlineXBRL-part0-WGN-2015-12-09.html)
# - [XBRL - Wikipedia](https://en.wikipedia.org/wiki/XBRL)
# 
# ### TODO: Create an Excel add-in
# - [Microsoft Excel add-in overview](https://docs.microsoft.com/en-us/office/dev/add-ins/excel/excel-add-ins-overview)
# - [xlwings for using Python w/Excel](https://www.xlwings.org/examples)

# ## Urls containing sample iXBRL docs
# - https://xbrl.us/xbrl-taxonomy/2019-cafr/
# 
# URLs that take too long to return data:
# - https://xbrlus.github.io/cafr/samples/8/va-c-bris-20160630.xhtml

# In[243]:


urls = ['https://xbrlus.github.io/cafr/samples/3/Alexandria-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/4/FallsChurch-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/5/Loudoun-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/6/ga-20190116.htm',
        'https://xbrlus.github.io/cafr/samples/1/StPete_StmtNetPos_iXBRL_20190116.htm',
        'https://xbrlus.github.io/cafr/samples/2/VABeach_StmtNetPos_iXBRL_20190116.htm',
        'https://xbrlus.github.io/cafr/samples/7/ut-20190117.htm']


# ## Libraries
# **BeautifulSoup**: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

# In[244]:


import re
import requests
from bs4 import BeautifulSoup
from pandas import Series, DataFrame
import pandas as pd
import numpy as np
import datetime

# In Python 3.7, dict is automatically ordered, but to allow for people using previous versions,
# need to use an OrderedDict or the results will be messy.
from collections import OrderedDict


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
    def string(self):
        # Optional scale attribute will be 0, 3 or 6, number needs to be multiplied by 10 ** scale.
        
        # Have to remove commas from the number (sigh).
        # A non-numeric value raises exception, we treat that case as a zero (often it's a dash character).
        try:
            number = int(self.tag.string.replace(',', ''))
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


class InputCriteria:
    ''' Represents input criteria for an output field from config.csv. '''
    # cafr:CashAndCashEquivalents (cafr:AccrualBasisOfAccountingMember cafr:GovernmentalTypeActivityMember cafr:PrimaryGovernmentActivitiesMember)
    regex = re.compile(r'(.*?)\s*\((.*?)\)')
    
    def __init__(self, text):
        result = self.regex.search(text)
        try:
            self.name = result.group(1)
            self.required_members = result.group(2).split()
        except:
            # Some criteria, such as cafr:DocumentName, don't have context info.
            self.name = text
            self.required_members = []
            
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


# In[263]:


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


# In[264]:


class SummarySpreadsheet:    
    def __init__(self, paths = [], urls = [], config_path = 'config.csv'):
        self.paths = paths
        self.urls = urls
        self.config_path = config_path
        self.docs = []
        
        # Load all specified documents.
        for path in paths:
            print(f'Loading {path}...')
            doc = XbrliDocument(path=path)
            self.docs.append(doc)

        for url in urls:
            print(f'Downloading {url}...')
            try:
                doc = XbrliDocument(url=url)
                self.docs.append(doc)
            except:
                pass

    def to_csv(self, path='output.csv'):
        self.dataframe.to_csv(path, index=False)

    def to_excel(self, path='output.xlsx', number_format='#,##0', col_width=45, freeze_cols=3):
        # To have numbers not be treated as strings in the Excel file, have to specify the type of the column.
        # Easy approach is to just try turning each column into a numeric column and see if it works
        # (it will fail if any value is not a number).
        df = self.dataframe

        num_cols = len(self.output_fields)
        num_rows = len(df)

        for col in df.columns:
            try:
                df[col] = self._to_numeric(df[col])
            except:
                pass
            
        # Add number formatting to the Excel file.
        # https://xlsxwriter.readthedocs.io/example_pandas_column_formats.html
        
        # Create a Pandas Excel writer using XlsxWriter as the engine.
        writer = pd.ExcelWriter(path, engine='xlsxwriter')
        df.to_excel(writer, sheet_name='Sheet1', index=False)
        workbook  = writer.book
        worksheet = writer.sheets['Sheet1']

        # Add at the right the following calculation:  
        #    General Fund Balance / General Fund Expenditure with the title General Fund Balance Ratio.  
        #    The formula would be S2 / U2 where 2 is replaced by the row number.  
        col_index = num_cols
        header_format = workbook.add_format({'align': 'center', 'bold': True, 'bg_color':'yellow', 'bottom':True, 'left':True, 'right':True})
        worksheet.write(0, col_index, 'General Fund Balance Ratio', header_format)
        
        formula_format = workbook.add_format({'bg_color':'yellow', 'num_format': '0.00'})
        for row_index in range(1,num_rows+1):
            # Excel indexes are 1-based.
            worksheet.write(row_index, col_index, f'=S{row_index+1} / U{row_index+1}', formula_format)
        
        # Apply column width and number format to all columns.
        num_format = workbook.add_format({'num_format': number_format})
        worksheet.set_column(0, num_cols, col_width, num_format)

        # Freeze the specified number of columns.
        if freeze_cols:
            worksheet.freeze_panes(0, freeze_cols)
        
        # Close the Pandas Excel writer and output the Excel file.
        writer.save()       

    @property
    def dataframe(self):
        # Build up data dictionary to become DataFrame.
        sheet_data = OrderedDict()
        
        # For each output field, go through each doc and get the value based on input fields
        for output_name, inputs in self.output_fields.items():
            values = []
            for doc in self.docs:
                # NOW:
                # The criteria may match more than one element in the document. In that case,
                # if the matching elements have a date in their contexts, choose the most recent date.
                # Otherwise choose the last element found.
                for criteria in inputs:
                    elements_found = []
                    for element in doc.ix_elements:
                        if criteria.matches_element(element):
                            elements_found.append(element)
                            
                    if elements_found:
                        # Sort elements found by the context date (if any) and take the most recent date.
                        # If no context dates, this means returning the last element found.
                        elements_found.sort(key = lambda element: element.context.period)
                        values.append(elements_found[-1].string)
                        break
                    
                # If no value for this output field, need an empty value.
                if not elements_found:
                    values.append('')
            sheet_data[output_name] = values         
        return DataFrame(sheet_data)

    @property
    def orig_dataframe(self):
        # Build up data dictionary to become DataFrame.
        sheet_data = OrderedDict()
        
        # For each output field, go through each doc and get the value based on input fields
        for output_name, inputs in self.output_fields.items():
            values = []
            for doc in self.docs:
                for criteria in inputs:
                    value_found = False
                    for element in doc.ix_elements:
                        # Could be this element or a child of it that matches.
                        if criteria.matches_element(element):
                            values.append(element.string)
                            value_found = True
                            break
                    if value_found:
                        break
                    
                # If no value for this output field, need an empty value.
                if not value_found:
                    values.append('')
            sheet_data[output_name] = values         
        return DataFrame(sheet_data)

    @property
    def output_fields(self):
        ''' 
        If the config CSV file exists, it is used to determine what to output.
        If config file doesn't exist, uses all fields specified in the docs.

        CSV Format:

        Output Field Name,Input Field Name (minimum required contexts)
        Document Title,cafr:DocumentTitle

        The same Output Field Name can be used multiple times, 
        to allow multiple Input Field Names tied to the same output name.
        In that case, only the first matching Input Field Name will be used for a document.

        Returns a dictionary with the output field name as the key and a list of InputCriteria objects as the value.
        '''
        try:
            return self._output_fields
        except:
            pass
        
        self._output_fields = OrderedDict()
        try:
            df = pd.read_csv(self.config_path)
            for output_name, input_name in df.itertuples(index=False):
                inputs = self._output_fields.setdefault(output_name, [])
                inputs.append(InputCriteria(input_name))
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
        for item in iterable:
            if isinstance(item, str):
                # Numeric conversions can't handle commas.
                item = item.replace(',', '')
                
                # Empty string will fail to convert, so turn it into NotANumber...
                if item == '': item = np.nan
            converted.append(item)
        return pd.to_numeric(converted, downcast=downcast)


# In[265]:


def main(paths=None):
    ''' For development, pass a list of paths and urls will be skipped. '''
    if paths:
        spreadsheet = SummarySpreadsheet(paths=paths)
    else:
        spreadsheet = SummarySpreadsheet(urls=urls)
    
    spreadsheet.to_csv()
    print('Generated output.csv')
    
    spreadsheet.to_excel()
    print('Generated output.xlsx')


# In[266]:


def test():
    from mydir import mydir
    from pathlib import Path
    
    paths = [str(path) for path in Path('test_data').iterdir() if '.xhtml' in str(path) or '.htm' in str(path)]
    main(paths)


# In[267]:


#main()
test()

