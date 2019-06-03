import pandas as pd
from pandas import Series, DataFrame, Index
from decimal import Decimal
from ixbrl import XbrliDocument

ixbrl_files = ['https://xbrlus.github.io/cafr/samples/20/Los_Angeles-20180630.htm', \
'https://xbrlus.github.io/cafr/samples/21/San_Diego-20180630.htm', \
'https://xbrlus.github.io/cafr/samples/22/Columbus-20171231.htm']

context = pd.DataFrame(columns=['contextref','dimension1','memberstring1','dimension2','memberstring2','instant','StartDate','EndDate'])
ixdata = pd.DataFrame(columns=['document','itemname','contextref','value'])

def display(text):
    ''' Returns a display-friendly version of the text. '''
    return text.replace('us-cafr:','').replace('Axis','').replace('Member','')

for fileloc in ixbrl_files:
    ixbrl_doc = XbrliDocument(url=fileloc)

    for context_obj in ixbrl_doc.contexts.values():
        dimension1 = dimension2 = memberstring1 = memberstring2 = ''

        for index, explicitmember in enumerate(context_obj.explicit_members.values()):
            if index == 0:
                dimension1 = display(explicitmember.dimension)
                memberstring1 = display(explicitmember.string)
            if index == 1:
                dimension2 = display(explicitmember.dimension)
                memberstring2 = display(explicitmember.string)

        context = context.append({'contextref': context_obj.id, 
                                  'dimension1': dimension1, 
                                  'memberstring1': memberstring1, 
                                  'dimension2': dimension2, 
                                  'memberstring2': memberstring2,
                                  'instant': context_obj.instant, 
                                  'StartDate': context_obj.start_date, 
                                  'EndDate': context_obj.end_date}, ignore_index=True)

    for ix_element in ixbrl_doc.ix_elements:
        if ix_element.tag.name.startswith('ix:non'):
            ixdata = ixdata.append({'document': fileloc, 
                                    'itemname': display(ix_element.name), 
                                    'contextref' : ix_element.contextref, 
                                    'value': ix_element.string}, ignore_index=True)

ixdata.to_csv('ixdata.csv', index=False)
taxonomy_extract = pd.read_csv('TaxonomyExtract.csv', encoding='windows-1252')
output=ixdata.merge(context, on='contextref').merge(taxonomy_extract, on='itemname').sort_values(by = ['document','itemname'])
output.drop_duplicates(keep='first',inplace=True) 
output.to_csv('output.csv', index=False)