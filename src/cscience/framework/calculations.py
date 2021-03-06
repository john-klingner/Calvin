"""
workflows.py

* Copyright (c) 2006-2015, University of Colorado.
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

import collections
import itertools
import re

import cscience.components
import cscience.datastore
from cscience.framework import Collection


factor_exp = re.compile('<(.*?)>')
def extract_factor(name):
    return factor_exp.search(name)[0]

class Workflow(object):
    """
    Defines a linkage between components, used to perform a series of
    calculations on a group of samples.
    
    Connections between components are defined in the format:
     {'source component': {'output port name': 'destination component',
                           'output port name': 'destination component'}
      'source component': ...}
    
    Factors will appear in connections as Factor<factor_name>.
    """
    
    #Things I want to be able to ask a workflow about:
    # required & optional inputs
    # outputs
    # parameters from paleobase (eg calibration curve to use)
    # list of applicable factors (done)

    def __init__(self, name):
        self.name = name
        self.connections = {}
        
    def add_component(self, component):
        self.connections.setdefault(component, {})
        
    def connect(self, fromcomponent, tocomponent, on_port='output'):
        """
        connect two components. Both components will be added to the workflow,
        if they are not already present.
        """
        self.add_component(fromcomponent)
        self.add_component(tocomponent)
        self.connections[fromcomponent][on_port] = tocomponent
        
    def find_parameters(self):
        #TODO: these have req'd fields, should return those too.
        params = set()
        for component in self.connections:
            params.update(getattr(cscience.components.library[component], 
                                  'params', {}).keys())
        return params

    def load_component(self, name, experiment):
        if name.startswith('Factor'):
            component = cscience.datastore.selectors[extract_factor(name)]
        else:
            component = cscience.components.library[name]()
        component.prepare(cscience.datastore.milieus, self, experiment)
        return component

    def get_factors(self):
        factors = set([extract_factor(name) for name in self.connections 
                       if name.startswith("Factor")])
        return list(factors)

    def instantiate(self, experiment):
        # Load & prepare an instance of every component to be used in this
        # workflow instance. Note that Factors handle their own instantiation
        # of their instance components.
        components = dict([(name, self.load_component(name, experiment)) 
                           for name in self.connections])
        # Loop through all components and connect them up according to
        # the information stored in self.connections.
        for component_name in self.connections:
            for port in self.connections[component_name]:
                target_name = self.connections[component_name][port]
                components[component_name].connect(components[target_name], port)
        return components
        
    def execute(self, cplan, core, aborting):
        components = self.instantiate(cplan)
        first_component = components[self.find_first_component()]

        # bad ass pythonic execution algorithm written by Evan Sheehan
        # gist: 
        #       1. create a queue that contains a tuple of the first
        #          component of the workflow and the set of samples
        #          to process
        #       2. pull the first tuple off the queue, get its component
        #          and pass the set of samples to it.
        #       3. When a component is invoked, it processes the set of
        #          samples handed to it and returns a tuple of the next
        #          component to execute and the samples it needs to process
        #       4. This tuple gets added to the queue and we continue
        #          to invoke components and add tuples to the queue until
        #          the queue is empty.
        #       Note: we only add a tuple to the queue if it a) has greater
        #             than zero samples to process and 2) is not already in
        #             the queue. This ensures that the queue eventually
        #             empties out.
        q = collections.deque([([first_component], core)])
        while q:
            if aborting():
                return False
            components, core = q.popleft()
            for pending in map(lambda comp: comp(core), components):
                for pair in pending:
                    if pair[0] and pair[1] and pending not in q:
                        q.append(pair)
                        
        for sample in core:
            sample.remove_exp_intermediates()
        return True

    def find_first_component(self):
        first_set = set(self.connections.keys())
        for dest in self.connections.itervalues():
            first_set -= set(dest.values())
        if len(first_set) == 1:
            return first_set.pop()
        raise KeyError("Workflow does not have a clear first component")


class Workflows(Collection):
    _filename = 'workflows'

class ComputationPlan(dict):
    def __init__(self, name):
        super(ComputationPlan, self).__init__(name=name)
        
    def __getattribute__(self, key):
        try:
            return self[key]
        except KeyError:
            #fallthrough -- if it's not a key, it might be a method
            return super(ComputationPlan, self).__getattribute__(key)

class ComputationPlans(Collection):
    _filename = 'cplans'
       
    def __iter__(self):
        return iter(sorted(self.values(), key=lambda x:x.name))

class Selector(dict):
    """A Selector in CScience is a placeholder within workflows that allow
    different components to be plugged into a workflow depending
    on the 'mode' of the factor.

    Operationally, an experiment allows a user to specify the
    different modes for all factors contained within a particular
    workflow. Each mode is associated with a different component.
    Once an experiment's factor modes have all been specified, the
    workflow object creates a workflow that plugs in the correct
    component for each factor.
       
    This behavior allows the same workflow to contain different code,
    so long as that code produces the same set of outputs from the
    same set of inputs (so, for example, we could use a different
    interpolation scheme in the same workflow).
    
    Note that one entry ("mode") in the Selector list can be a list of
    components. In this case the listed components will be executed in
    sequence when that mode is selected for the Selector.
    """

    def __init__(self, name):
        self.name = name
    def __getstate__(self):
        #this keeps us from saving the current faux-component state when this
        #Selector is saved. Only the name and dict-contents are saved.
        return {'name', self.name}

    def prepare(self, collections, workflow, experiment):
        #NOTE: this assumes that all 'Selector' entries will be iterable, even
        #if there is only one item in said entry!
        names = self[experiment[self.name]]
        components = dict.fromkeys(names)
        for name in components:
            component = cscience.components.library[name]()
            component.prepare(collections, workflow, experiment)
            components[name] = component
        #Now that we have all the components, let's go ahead and hook them up
        #in order as part of preparation
        #See python doc itertools pairwise recipe if needed.
        source, dest = itertools.tee(names)
        next(dest, None)
        for s, d in itertools.izip(source, dest):
            components[s].connect(components[d])
            
        #save input & output components for connecting outside this Selector
        self.input = components[names[0]]
        self.output = components[names[-1]]
            
    def connect(self, component, name='output'):
        #Assumes Selector will have been prepared ahead of connections
        self.output.connect(component, name)
        
    def input_port(self):
        #Assumes Selector will have been prepared ahead of connections
        return self.input

class Selectors(Collection):
    _filename = 'selectors'

