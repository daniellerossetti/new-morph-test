"""
This script performs a morphological test on a yaml file (that has a certain format).
Author: Danielle Rossetti Dos Santos
"""

from argparse import ArgumentParser
from collections import OrderedDict
from io import StringIO

import sys 
import libhfst
import yaml
import textwrap 

# defining a few strings that are used often
pass_mark = '{green}[✓]{reset}'
fail_mark = '{red}[✗]{reset}'
na_mark = ' - '

def error_checking(n):
    """
    Current function for printing error messages and exiting.
    parameters: n - corresponds to a particular error (makes it easier to find)
    """
    msg = 'Error {}: '.format(n)
    if n == 2:   msg += 'there was an error opening the file provided.'
    elif n == 3: msg += 'outer sections of file should be "Config" and "Tests".'
    elif n == 4: 
      msg += 'within "Config", there should be an "hfst" section, which in '
      msg += 'turn should have a "Morph" and a "Gen" section.'
    elif n == 5: 
      msg += 'make sure items under "Tests" are mappings and follow the format.'
    elif n == 6: msg += 'possible direction arrows are =>, <=, or <=>.'
    elif n == 7: msg += 'the section requested does not exist.'
    elif n == 8: msg += 'the output options are: normal, compact, final, none.'
    print(msg)
    sys.exit(n)

def argument_parsing():
    ap = ArgumentParser()
    ap.description = 'This script performs a morphological test.'
    
    h = 'Output style:\n'
    h += '*normal (TP, TN, FP, FN for each analysis and generationt test)\n'
    h += '*compact (whether sections passed or failed)\n'
    h += '*final (total number of passes, fails, and overall tests)\n'
    h += '*none (no output, only exit code)\n'
    h += '(Default: normal)'
    ap.add_argument('-o', '--output', dest='output', default='normal', help=h)
    
    h = 'Ignores analysis false positives. '
    h += 'Will pass if expected results are found.'
    ap.add_argument('-ia', '--ignore-extra-analyses',
                    dest='ignore_ana', action='store_true', help=h)

    h = 'Ignores generation false positives. '
    h += 'Will pass if expected results are found.'
    ap.add_argument('-ig', '--ignore-extra-generations',
                    dest='ignore_gen', action='store_true', help=h)
    
    # removed 'hide fails' option because not sure if people used it at all
    h = 'Suppresses passes to make finding failures easier'
    ap.add_argument('-f', '--hide-passes', dest='hide_pass', 
                    action='store_true', help=h)

    h = 'Section to run tests on (Default: all). Enter the # of the section.'
    ap.add_argument('-t', '--test', dest='test', type=int, default='-1', help=h)
  
    ap.add_argument('-v', '--verbose', dest='verbose', action='store_true', 
                    help='More verbose output.')
    
    ap.add_argument('test_file', help='YAML file with test rules')
    arguments = ap.parse_args()
    return arguments

def define_colors():
    colors = {}
    colors['red'] = '\033[0;31m'
    colors['green'] = '\033[0;32m'
    colors['grey'] = '\033[0;37m'
    colors['reset'] = '\033[m'
    return colors

# Courtesy of https://gist.github.com/844388. Thanks!
class _OrderedDictYAMLLoader(yaml.Loader):
    """A YAML loader that loads mappings into ordered dictionaries."""

    def __init__(self, *args, **kwargs):
        yaml.Loader.__init__(self, *args, **kwargs)

        self.add_constructor('tag:yaml.org,2002:map', type(self).construct_yaml_map)
        self.add_constructor('tag:yaml.org,2002:omap', type(self).construct_yaml_map)

    def construct_yaml_map(self, node):
        data = OrderedDict()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)
        else:
            raise yaml.constructor.ConstructorError(None, None,
                'expected a mapping node, but found %s' % node.id, node.start_mark)

        mapping = OrderedDict()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node)
            value = self.construct_object(value_node)
            mapping[key] = value
        return mapping

def yaml_load_ordered(f):
    return yaml.load(f, _OrderedDictYAMLLoader)

class MorphTest:
    """
    Holds information about each direction of a particular morphological test.
    """
    def __init__(self, left, right, direction):
        self.left = left
        self.direction = direction 
        self.right = right
        self.hide_passes = False

        # these will be added when running the tests
        self.ana_result = []
        self.gen_result = []
      
        # used for determining if test passed analysis
        self.ana_tn = True
        self.ana_fp = []
        self.ana_missing = True
        self.ignore_ana_fp = False

        # used for determining if test passed generation
        self.gen_tn = True
        self.gen_fp = []
        self.gen_missing = True
        self.ignore_gen_fp = False

    def passed_analysis(self):
        # did analysis pass?
        if not self.ana_missing and (self.ana_tn or self.ana_tn is None):
          if self.ignore_ana_fp: return True
          elif not len(self.ana_fp): return True
        return False

    def passed_generation(self):
        # did generation pass?
        if not self.gen_missing and (self.gen_tn or self.gen_tn is None):
          if self.ignore_gen_fp: return True
          elif not len(self.gen_fp): return True
        return False

    def get_test_results(self):
      """ 
      Creates string containing the information about the test.
      """
      # starting with test
      # if passes don't need to be hidden or one direction has failed: 
      if not self.hide_passes or \
      not (self.passed_analysis() and self.passed_generation()): 
        s = '{:<45}\n '.format(self.left+' '+self.direction+' '+self.right) 
  
      if not self.hide_passes or not self.passed_analysis():
        # analysis check mark
        if self.passed_analysis(): s += pass_mark
        else: s += fail_mark
        s += ' Analysis:' + ' '*25

        # analysis tp, tn, fp, fn row
        # true positive:
        if self.ana_missing: s += fail_mark
        elif self.ana_missing == None: s += na_mark
        else: s += pass_mark
        s += ' '*9

        # true negative:
        if self.ana_tn: s += pass_mark
        elif self.ana_tn == None: s += na_mark
        else: s += fail_mark
        s += ' '*9

        # false positive:
        if self.ignore_ana_fp: s += na_mark
        else:
          if not len(self.ana_fp): s += pass_mark
          else: s +=  fail_mark
        s += ' '*9

        # false negative:
        if self.ana_missing: s += fail_mark
        elif self.ana_missing == None: s += na_mark
        else: s += pass_mark
        s += '\n '

      if not self.hide_passes or not self.passed_generation():
        # generation check mark
        if self.passed_generation(): s += pass_mark
        else: s += fail_mark
        s += ' Generation:' + ' '*23
      
        # generation tp, tn, fp, fn row 
        # true positive:
        if self.gen_missing: s += fail_mark
        elif self.gen_missing == None: s += na_mark
        else: s += pass_mark
        s += ' '*9

        # true negative:
        if self.gen_tn: s += pass_mark
        elif self.gen_tn == None: s += na_mark
        else: s += fail_mark
        s += ' '*9

        # false positive:
        if self.ignore_gen_fp: s += na_mark
        else:
          if not len(self.gen_fp): s += pass_mark
          else: s +=  fail_mark
        s += ' '*9

        # false negative:
        if self.gen_missing: s += fail_mark
        elif self.gen_missing == None: s += na_mark
        else: s += pass_mark
        s += '\n'
      
      # comments
      if not self.passed_analysis() or not self.passed_generation(): 
        c = ' Comments: {grey}'
        if not self.passed_analysis():
          # analysis:
          if self.ana_missing: c += 'analysis is missing {}. '.format(self.left)
          if self.ana_tn == False: c += '{} was generated. '.format(self.right)
          if len(self.ana_fp):
            c += 'analysis returned unexpected result'
            if len(self.ana_fp) > 1:
              c += 's: '
              for analysis in self.ana_fp[:-1]:
                c += '{}, '.format(analysis)
              c += 'and {}.'.format(self.ana_fp[-1])
            elif len(self.ana_fp) == 1: c += ': {}. '.format(self.ana_fp[0])       
        
        if not self.passed_generation():
          #generation:
          if self.gen_missing: 
            c += 'generation is missing {}. '.format(self.right)
          if self.gen_tn == False: c += '{} was analyzed. '.format(self.left)
          if len(self.gen_fp):
            c += 'generation returned unexpected result'
            if len(self.gen_fp) > 1:
              c += 's: '
              for generation in self.gen_fp[:-1]:
                c += '{}, '.format(generation)
              c += 'and {}.'.format(self.gen_fp[-1])
            elif len(self.gen_fp) == 1: c += ': {}.'.format(self.gen_fp[0])
        c += '{reset}\n\n'

        # formatting comments better 
        c = textwrap.fill(c, 69)
        c = c.replace('\n', '\n ')
        c += '\n\n'

      else: c = '\n' # if there are no comments
      if self.hide_passes and self.passed_analysis() and self.passed_generation():
        s, c = '', ''
      return s + c

class Section:
    """
    Holds information about the tests in a particular section of the .yaml file.
    """
    def __init__(self, title, number, mappings):
        self.title = title
        self.number = number
        self.mappings = mappings 
        self.tests = self.populate_tests()
        self.ana_passes, self.ana_fails = 0, 0
        self.gen_passes, self.gen_fails = 0, 0

    def populate_tests(self):
        tests = []
        # for each 'left (direction) right' mapping:
        for left in self.mappings:
          for map_direction, right in self.mappings[left].items():
            # if there are multiple items
            if isinstance(right, list):
              for item in right:
                if map_direction in ['=>', '<=', '<=>']:
                  tests.append(MorphTest(left, item, map_direction))
                else: error_checking(6)
            # if there is only one item
            else:
              if map_direction in ['=>', '<=', '<=>']:
                  tests.append(MorphTest(left, right, map_direction))
              else: error_checking(6)
       
        return tests 

    def get_counts(self):
        # gets section's pass count and fail count for analysis and generation
        for test in self.tests:
          if test.passed_analysis(): self.ana_passes += 1
          else: self.ana_fails += 1
          if test.passed_generation(): self.gen_passes += 1
          else: self.gen_fails += 1
    
    def create_output(self, normal_style=True):
        # this function is only used for normal or compact style output
        # make section header into a string
        s = '{grey}-'*80 + '{reset}\n'
        s += '{}\nTests - section #{:<17}'.format(self.title, self.number)
        if normal_style: s += 'True pos    True neg   False pos   False neg\n'
        else: s += ' '*46 # compact
        s += '{grey}-'*80 + '{reset}\n'
 
        # normal output style
        if normal_style:
          # make test results into strings
          for test in self.tests:
            s += test.get_test_results()
        
        # make passes and fails counts into strings
        if not normal_style: # compact
          if self.ana_fails: s += '{} '.format(fail_mark)
          else: s += '{} '.format(pass_mark)

        s += 'Analysis - {}: {}, '.format(pass_mark, self.ana_passes)
        s += '{}: {}'.format(fail_mark, self.ana_fails)

        if normal_style: s += ' / ' # same line if normal 
        else:  # compact
          if self.gen_fails: s += '\n{} '.format(fail_mark)
          else: s += '{} '.format(pass_mark)

        s += 'Generation - {}: {}, '.format(pass_mark, self.gen_passes)
        s += '{}: {}\n\n'.format(fail_mark, self.gen_fails)
        
        return s

class Results:
    """
    Performs the tests and holds the list of Sections. 
    """
    def __init__(self, sections_list, morph, gen, args):
        # these dictionaries help ensure false positives 
        # are actually false positives
        self.analysis_dict = {}
        for section in sections_list:
          for test in section.tests:
            if test.right in self.analysis_dict:
              self.analysis_dict[test.right].append(test.left)
            else: self.analysis_dict[test.right] = [test.left]
  
        self.generation_dict = {}
        for section in sections_list:
          for test in section.tests:
            if test.right in self.generation_dict:
              self.analysis_dict[test.left].append(test.right)
            else: self.generation_dict[test.left] = [test.right]
        
        self.sections = sections_list
        self.morph_path = morph
        self.gen_path = gen
        self.args = args

        # printing stuff
        self._io = StringIO()
        self.colors = define_colors()
        self.ana_passes, self.ana_fails = 0, 0
        self.gen_passes, self.gen_fails = 0, 0

    def __str__(self):
        return self._io.getvalue()
    
    def color_write(self, string, *args, **kwargs):
        kwargs.update(self.colors)
        self._io.write(string.format(*args, **kwargs))

    def get_total_counts(self):
        for section in self.sections:
          self.ana_passes += section.ana_passes 
          self.ana_fails += section.ana_fails
          self.gen_passes += section.gen_passes
          self.gen_fails += section.gen_fails
    
    def print_normal(self): 
        if self.args.test >= 0:
          self.color_write(self.sections[self.args.test].create_output())
        else:
          for section in self.sections:
            self.color_write(section.create_output())
        self.print_final()

    def print_compact(self):
        if self.args.test >= 0:
          section = self.sections[self.args.test]
          self.color_write(section.create_output(normal_style=False))
        else:
          for section in self.sections:
            self.color_write(section.create_output(normal_style=False))
        self.print_final()

    def print_final(self):
        if self.args.test >= 0:
          section = self.sections[self.args.test]
          # get the section's counts
          self.ana_passes = section.ana_passes
          self.ana_fails = section.ana_fails
          self.gen_passes = section.gen_passes
          self.gen_fails = section.gen_fails 

        # make passes and fails counts into strings 
        s = 'Overall results:\n'
        if self.ana_fails: s += ' {0} '.format(fail_mark)
        else: s += '{0} '.format(pass_mark)

        s += 'Analysis - {0}: {1}, '.format(pass_mark, self.ana_passes)
        s += '{0}: {1}\n'.format(fail_mark, self.ana_fails)

        if self.gen_fails: s += ' {0} '.format(fail_mark)
        else: s += '{0} '.format(pass_mark)

        s += 'Generation - {0}: {1}, '.format(pass_mark, self.gen_passes)
        s += '{0}: {1}'.format(fail_mark, self.gen_fails)
        self.color_write(s)

    def lookup(self):
        # getting analysis data used in test
        analysis_stream = libhfst.HfstInputStream(self.morph_path).read()
        for section in self.sections:
          for test in section.tests:
            for result in analysis_stream.lookup(test.right):
              test.ana_result.append(result[0])
        
        # getting generation data used in test
        generation_stream = libhfst.HfstInputStream(self.gen_path).read()
        for section in self.sections:  
          for test in section.tests:
            for result in generation_stream.lookup(test.left):
              test.gen_result.append(result[0])
          
    def run_analysis_tests(self, section):
        if self.args.verbose: print('Running analysis tests...')
        for test in section.tests:
          if self.args.ignore_ana: test.ignore_ana_fp = True
          for result in test.ana_result:
            if test.direction == '<=' or test.direction == '<=>':
              if result == test.left: 
                # true positive was found
                test.ana_missing = False
              elif result not in self.analysis_dict[test.right]:
                # if not in dict it's false positive 
                test.ana_fp.append(result)
              if test.direction == '<=>':
                # there can't be a true negative
                test.ana_tn = None
            else: # test is generation only =>
              # analysis missing is a good thing here so N/A
              test.ana_missing = None
              if result == test.left:
                # this shouldn't happen, so true negative fails
                test.ana_tn = False

    def run_generation_tests(self, section):
        if self.args.verbose: print('Running generation tests...')
        for test in section.tests:  
          if self.args.ignore_gen: test.ignore_gen_fp = True
          for result in test.gen_result:
            if test.direction == '=>' or test.direction == '<=>':
              if result == test.right:
                # true positive was found
                test.gen_missing = False
              elif result not in self.generation_dict[test.left]:
                #if not in dict it's false positive
                test.gen_fp.append(result)
              if test.direction == '<=>':
                # there can't be a true negative
                test.gen_tn = None
            else: # test is analysis only <=
              # analysis missing is a good thing here so N/A
              test.gen_missing = None
              if result == test.right:
                # this shouldn't happen, so true negative fails
                test.gen_tn = False

    def run(self):
        self.lookup()
        if self.args.test >= 0:
          if self.args.test > len(self.sections) - 1: error_checking(7)
          if self.args.verbose:
            print('Running tests on section #{0}'.format(self.args.test))
          section = self.sections[self.args.test]
          
          # runnning tests
          self.run_analysis_tests(section)
          self.run_generation_tests(section)
        else:
          for section in self.sections:
            if self.args.verbose: 
              print('Running tests on section #{0}'.format(section.number))
                
            # running tests
            self.run_analysis_tests(section)
            self.run_generation_tests(section)
        
        # if passes are to be hidden
        if self.args.hide_pass:
          for section in self.sections:
            for test in section.tests:
              test.hide_passes = True
        
        # getting all counts 
        for section in self.sections:
          section.get_counts()
        self.get_total_counts()

        # type of output
        if self.args.output == 'normal': self.print_normal()
        elif self.args.output == 'compact': self.print_compact()
        elif self.args.output == 'final': self.print_final()
        elif self.args.output != 'none': error_checking(8)
        print(self)

        # exit code
        if self.args.test >= 0:
          section = self.sections[self.args.test]
          if section.ana_fails or section.gen_fails: return 1
          else: return 0
        else: # all
          if self.ana_fails or self.gen_fails: return 1
          else: return 0

def load_data(args):
    try: yaml_file = open(args.test_file, 'r')
    except: error_checking(2)
    if args.verbose: print('Opened file.')
  
    # creating an ordered dictionary from the yaml file
    dictionary = yaml_load_ordered(yaml_file)
    yaml_file.close()
    if args.verbose: print('Created dictionary from yaml file.')
      
    # ensure dictionary contains only config and tests
    if not dictionary['Config'] or not dictionary['Tests']: error_checking(3)
    if len(dictionary) != 2: error_checking(3)

    try:
      # getting config - script currently only works with .hfst files
      hfst_config = dictionary['Config']['hfst']
      morph = hfst_config['Morph']
      gen = hfst_config['Gen']

      # getting tests
      tests = dictionary['Tests']
    except: error_checking(4)

    all_sections = []
    for num, title in enumerate(tests):
      # error if tests[title] isn't an ordered dictionary
      if not isinstance(tests[title], OrderedDict): error_checking(5)
      section = Section(title, num, tests[title])
      all_sections.append(section)
    if args.verbose: print('Created section objects.')

    return all_sections, morph, gen

def main(): 
    args = argument_parsing()
    sections, morph, gen = load_data(args)
    if args.verbose: print('Getting results...')
    results = Results(sections, morph, gen, args)
    return results.run()

if __name__ == "__main__":
    main()
