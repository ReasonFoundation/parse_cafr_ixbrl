#!/usr/bin/env python

'''
getix.py

This script is an in-progress effort to make it easy to parse iXBRL files and generate spreadsheet output (Excel and CSV).
This script will soon be phased out in favor of cafr_excel.py.

Resources
- iXBRL spec: http://www.xbrl.org/specification/inlinexbrl-part1/rec-2013-11-18/inlinexbrl-part1-rec-2013-11-18.html
- [iXBRL schema](http://www.xbrl.org/specification/inlinexbrl-part2/rec-2013-11-18/inlinexbrl-part2-rec-2013-11-18.html)
- [iXBRL primer](http://www.xbrl.org/WGN/inlineXBRL-part0/WGN-2015-12-09/inlineXBRL-part0-WGN-2015-12-09.html)
- [XBRL - Wikipedia](https://en.wikipedia.org/wiki/XBRL)

Libraries
- BeautifulSoup: https://www.crummy.com/software/BeautifulSoup/bs4/doc/

'''


urls = ['https://xbrlus.github.io/cafr/samples/3/Alexandria-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/4/FallsChurch-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/5/Loudoun-2018-Statements.htm',
        'https://xbrlus.github.io/cafr/samples/6/ga-20190116.htm',
        'https://xbrlus.github.io/cafr/samples/1/StPete_StmtNetPos_iXBRL_20190116.htm',
        'https://xbrlus.github.io/cafr/samples/2/VABeach_StmtNetPos_iXBRL_20190116.htm',
        'https://xbrlus.github.io/cafr/samples/7/ut-20190117.htm']



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

from ixbrl import Criterion, XbrliDocument



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
        #    The formula would be R2 / T2 where 2 is replaced by the row number.  
        col_index = num_cols
        header_format = workbook.add_format({'align': 'center', 'bold': True, 'bg_color':'yellow', 'bottom':True, 'left':True, 'right':True})
        worksheet.write(0, col_index, 'General Fund Balance Ratio', header_format)
        
        formula_format = workbook.add_format({'bg_color':'yellow', 'num_format': '0.00'})
        for row_index in range(1,num_rows+1):
            # Excel indexes are 1-based.
            worksheet.write(row_index, col_index, f'=R{row_index+1} / T{row_index+1}', formula_format)
        
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

