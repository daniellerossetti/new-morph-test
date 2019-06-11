"""
**to dos:
  - implement hide fails+passes, output types
  - make sure tests are actually working now 
  -    # add 'do not analyse' negation (for spellchecker testing)
This script performs a morphological test on a file.
Author: Danielle Rossetti Dos Santos
"""
from argparse import ArgumentParser
from collections import OrderedDict
from io import StringIO
import libhfst
import sys
import yaml
import time 

pass_mark = '{green}[✓]{reset}'
fail_mark = '{red}[✗]{reset}'
na_mark = ' - '

def error_checking(n):
    msg = 'Error: '
    if n == 2:   msg += 'there was an error opening the file provided.'
    elif n == 3: msg += 'outer sections of file should be "Config" and "Tests".'
    elif n == 4: 
      msg += 'within "Config", there should be an "hfst" section, which in '
      msg += 'turn should have a "Morph" and a "Gen" section.'
    elif n == 5: 
      msg += 'make sure items under "Tests" are mappings and follow the format.'
    elif n == 6: msg += 'possible direction arrows are =>, <=, or <=>.'
    elif n == 7: msg += 'the section requested does not exist.'
    print(msg)
    sys.exit(num)

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

    ap.add_argument('-p', '--hide-fails', dest='hide_fail', action='store_true',                    help='Suppresses fails to make finding passes easier.')

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
    colors['yellow'] = '\033[0;33m'
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
    def __init__(self, left, right, direction):
        self.left = left
        self.direction = direction 
        self.right = right
        self.passed_analysis = False
        self.passed_generation = False

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

    def get_test_results(self):
      # did analysis pass?
      if not self.ana_missing and (self.ana_tn or self.ana_tn is None):
        if self.ignore_ana_fp: self.passed_analysis = True
        elif not len(self.ana_fp): self.passed_analysis = True

      # did generation pass?
      if not self.gen_missing and (self.gen_tn or self.gen_tn is None):
        if self.ignore_gen_fp: self.passed_generation = True
        elif not len(self.ana_fp): self.passed_analysis = True

      # starting with test
      s = '{0:<45}\n '.format(self.left+' '+self.direction+' '+self.right) 
      
      # analysis check mark
      if self.passed_analysis: s += pass_mark
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

      # generation check mark
      if self.passed_generation: s += pass_mark
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
      if not self.passed_analysis or not self.passed_generation: 
        c = ' {yellow}Comments: '
        # analysis:
        if self.ana_missing: c += 'analysis is missing {0}. '.format(self.left)
        if self.ana_tn == False: c += '{0} was generated. '.format(self.right)
        if len(self.ana_fp):
          c += 'analysis returned unexpected result'
          if len(self.ana_fp) > 1:
            c += 's: '
            for analysis in self.ana_fp[:-1]:
              c += '{0}, '.format(analysis)
            c += 'and {0}.'.format(self.ana_fp[-1])
          elif len(self.ana_fp) == 1: c += ': {0}. '.format(self.ana_fp[0])       
        # generation:
        if self.gen_missing: 
          c += 'generation is missing {0}. '.format(self.right)
        if self.gen_tn == False: c += '{0} was analyzed. '.format(self.left)
        if len(self.gen_fp):
          c += 'generation returned unexpected result'
          if len(self.gen_fp) > 1:
            c += 's: '
            for generation in self.gen_fp[:-1]:
              c += '{0}, '.format(generation)
            c += 'and {0}.'.format(self.gen_fp[-1])
          elif len(self.gen_fp) == 1: c += ': {0}.'.format(self.gen_fp[0])
        c += '{reset}\n\n'
      else: c = '\n'
      return s + c

class Section:
    def __init__(self, title, number, mappings):
        self.title = title
        self.number = number
        self.mappings = mappings 
        self.passes = 0
        self.fails = 0
        self.tests = self.populate_tests()

    def populate_tests(self):
        tests = []

        # for each left (direction) right mapping:
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
    
    def __str__(self):
        # make section header into a string
        s = '{yellow}-'*80 + '{reset}\n'
        s += '{0}\nTests - section #{1:<17}'.format(self.title, self.number)
        s += 'True pos    True neg   False pos   False neg\n'
        s += '{yellow}-'*80 + '{reset}\n'

        # make tests in section into strings
        for test in self.tests:
            s += test.get_test_results()

        # make passes and fails counts into strings
        s += 'Passes: {0}{1}{2}, '.format('{green}', self.passes, '{reset}')
        s += 'Fails: {0}{1}{2}\n\n'.format('{red}', self.fails, '{reset}')
        return s

class Results:
    def __init__(self, sections_list, morph, gen, args):
        # these dictionaries help ensuring there aren't false positives
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
        self.fails = 0
        self.passes = 0

    def __str__(self):
        return self._io.getvalue()
    
    def color_write(self, string, *args, **kwargs):
        kwargs.update(self.colors)
        self._io.write(string.format(*args, **kwargs))
    
    def print_normal(self): 
        pass

    def print_compact(self):
        pass

    def print_final(self):
        s = 'Total passes: {0}{1}{2}'.format('{green}', self.passes, '{reset}')
        s += ', Total fails: {0}{1}{2}'.format('{red}', self.fails, '{reset}')
        self.color_write(s)

    def print_nothing(self):
        if self.fails > 0:
            return 1
        else:
            return 0

    def print_section(self, section):
        self.color_write(str(section))

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
          self.run_analysis_tests(section)
          self.run_generation_tests(section)
          self.print_section(section)
          self.print_final()
        else:
            for section in self.sections:
                if self.args.verbose: 
                  print('Running tests on section #{0}'.format(section.number))
                self.run_analysis_tests(section)
                self.run_generation_tests(section)
                self.print_section(section)
            self.print_final()
        print(self)
          

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
    results.run()

if __name__ == "__main__":
    main()

