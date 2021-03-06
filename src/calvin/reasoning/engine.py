"""
engine.py

* Copyright (c) 2006-2009, University of Colorado.
* All rights reserved.
*
* Redistribution and use in source and binary forms, with or without
* modification, are permitted provided that the following conditions are met:
*     * Redistributions of source code must retain the above copyright
*       notice, this list of conditions and the following disclaimer.
*     * Redistributions in binary form must reproduce the above copyright
*       notice, this list of conditions and the following disclaimer in the
*       documentation and/or other materials provided with the distribution.
*     * Neither the name of the University of Colorado nor the
*       names of its contributors may be used to endorse or promote products
*       derived from this software without specific prior written permission.
*
* THIS SOFTWARE IS PROVIDED BY THE UNIVERSITY OF COLORADO ''AS IS'' AND ANY
* EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
* WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
* DISCLAIMED. IN NO EVENT SHALL THE UNIVERSITY OF COLORADO BE LIABLE FOR ANY
* DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
* (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
* LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
* ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
* (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
* SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


import rule_list
import rules
import conclusions
import arguments
import samples


def explainAges():
    """
    Attempts to explain ages and stuff.
    """
    
    result = [(buildArgument(conclusion)).toEvidence() 
               for conclusion in conclusions.getConclusions()]
        
    return result
    
def buildArgument(conclusion):
    """
    builds an argument for the conclusion given. The conclusion should contain "filled" parameters,
    if it has any parameters.
    """
    
    ruleList = rules.getRules(conclusion)
    runRules = []
    
    #list of rules might be long, let's try to avoid killing too much memory
    for rule in ruleList:
        #print samples.initEnv
        try:
            if rule.canRun(conclusion):
                runRules.append(rule.run(conclusion))
        except KeyError:
            print 'still getting KeyErrors, I guess'
            """
            This fab error means we tried to do something with some data that the user didn't enter.
            We just silently fail for the moment. Frankly I think this is a much more elegant way to
            handle the issue I've been running into here.
            Also useful: later we can save these rules and use them to say something about what sort
            of new data might change our conclusions.
            """
            pass
    
    return arguments.Argument(conclusion, runRules)
    
    
