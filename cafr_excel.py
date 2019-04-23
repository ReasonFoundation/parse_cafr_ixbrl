import logging
from pathlib import Path

import xlwings as xw

from ixbrl import Criterion, XbrliDocument

class Spreadsheet:
    ''' Represents an Excel spreadsheet using xlwings. '''
    def __init__(self, workbook=None, sheet=None):
        if workbook:
            self.workbook = workbook
        else:
            self.workbook = xw.Book.caller()
        
        if sheet:
            self.sheet = sheet
        else:
            self.sheet = self.workbook.sheets[0]
                
    def column(self, index, count=50):
        ''' Returns count values from the specified column (1-based index!) '''
        # Excel ranges are (row, column).
        # Would prefer to use options(ndim=1,expand='down') but that stops at first blank cell.
        return self.sheet.range((1,index), (count,index)).value

    def row(self, index, count=50):
        ''' Returns count values from the specified row (1-based index!) '''
        # Excel ranges are (row, column).
        return self.sheet.range((index,1), (index,count)).value
    
    def cell(self, column, row):
        ''' Returns the value for the specified cell (1-based index!). '''
        return self.sheet.range((row, column)).value
       

class CAFRSpreadsheet(Spreadsheet):
    ''' Represents a CAFR Excel spreadsheet. '''
    def __init__(self, workbook=None, sheet=None):
       super().__init__(workbook, sheet)
       self._urls = None
       self._criteria = None
 
    @property
    def urls(self):
        '''
        A dictionary of URLs found in the first column.
        
        For debugging and local usage, a url starting with file: will be treated as a local path to a file.
        
        key: URL
        value: Excel row where URL was found (1-based index!)
        '''
        if self._urls is None:
            self._urls = {}

            # Using expand is stopping at the first blank entry.
            #column = self.sheet.range('A1').options(ndim=1, expand='down').value           
            for row, value in enumerate(self.column(1), start=1):
                if value and (value.startswith('http') or value.startswith('file')):
                    self._urls[value] = row
        return self._urls
    
    @property
    def criteria_for_columns(self):
        ''' A list of the criterion for each column.
            Each entry is a list of criterion for that column. '''
        if self._criteria is None:
            self._criteria = []
            for col_index, value in enumerate(self.row(1), start=1):
                if not value:
                    break

                # Get rid of any extra spaces
                value = value.strip()
                
                if value.startswith('us-cafr'):                    
                    # Each entry will be a list of requirements.
                    context_requirements = []
                    
                    # Look at the entries in this column for criterion context requirements.
                    # Start at second row.
                    for possible_requirement in self.column(col_index)[1:]:
                        if not possible_requirement or not possible_requirement.startswith('us-cafr'):
                            break
                        
                        requirements = possible_requirement.split()
                        context_requirements.append(requirements)
                    
                    entries = []
                    
                    if context_requirements:
                        for requirement in context_requirements:
                            criterion = Criterion(value, requirement)
                            entries.append(criterion)
                    else:                            
                        criterion = Criterion(value)
                        entries.append(criterion)
                    self._criteria.append(entries)
                    logging.debug(f'Criterion for column {col_index}: {entries}')
        return self._criteria
        
    
def update():
    excel = CAFRSpreadsheet()
    
    for url, index in excel.urls.items():
        if url.startswith('http'):
            doc = XbrliDocument(url=url)
        elif url.startswith('file'):            
            path = url.replace('file:', '')
            file = Path(path)
            
            '''
            If it's a relative path, figure out the full path to the file.
            When this script is called from Excel, the current working directory is the root directory (at least on Mac).
            __file__ contains the script path.
            '''
            if not file.is_absolute():
                script_path = Path(__file__).parent
                path = Path(script_path, file).absolute()
            
            logging.debug(f"Loading document: {path}")
            doc = XbrliDocument(path=path)
        else:
            raise ValueError(f"Unsupported URL: {url}")
        
        values = []
        for crit_list in excel.criteria_for_columns:
            elements_found = []
            for criterion in crit_list:
                logging.debug(f"Checking criterion: {criterion}")
                for element in doc.ix_elements:
                    if criterion.matches_element(element):
                        logging.debug(f"Matched: {element}")
                        elements_found.append(element)
                
            if elements_found:
                # Sort elements found by the context date (if any) and take the most recent date.
                # If no context dates, this means returning the last element found.
                elements_found.sort(key = lambda element: element.context.period)
                logging.debug(f"Value: {elements_found[-1].string}")
                values.append(elements_found[-1].string)        
            else:
                values.append('')

        # Update the spreadsheet for this URL.
        logging.debug(f"Values for row: {values}")
        excel.sheet.range((index, 2)).value = values

def clear():
    excel = CAFRSpreadsheet()
    for url, row in excel.urls.items():
        excel.sheet.range((row, 2)).expand('right').clear_contents()

def script_directory():
    # https://stackoverflow.com/questions/2632199/how-do-i-get-the-path-of-the-current-executed-file-in-python/18489147#18489147
    import inspect
    filename = inspect.getframeinfo(inspect.currentframe()).filename
    path     = os.path.dirname(os.path.abspath(filename))
    return path

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    # For debugging, can specify which file is the caller.
    xw.Book('cafr_excel.xlsm').set_mock_caller()
    update()
