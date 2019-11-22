# Morphological testing for HFST

## Pre-requisites
This was created for Apertium usage, though if you have another HFST transducer this will work just fine. You will need to have 'libhfst' and 'yaml' installed in order to use this.

## Instructions
1. Create a YAML file with the following format, where "=>" stands for generation and "<=" stands for analysis (this is just a meaningless example file).
``` 
Config:
  hfst:
    App: hfst-lookup
    Gen: <file where your generator is>
    Morph: <file where your analyzer is>
Tests:
  <section name>:
    hello<ij>:
      <=>: hello
    hiya<ij>:
      <=: hello
      =>: hi
      <=>: hey 
      <=:
        - good morning<ij>
        - good night<ij>
```
2. run program! That easy. Options for arguments are listed in help. The result of the test will be output through the standard out stream.

Note: the testing files I have included in this repository don't mean anything. They were just words I had on hand at the time and doesn't not reflect real rules for a language.
