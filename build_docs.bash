#!/bin/bash

pyreverse -o dot -p docs/dependency_graph.dot . 
dot -Tsvg docs/dependency_graph.dot -o docs/dependency_graph.svg

