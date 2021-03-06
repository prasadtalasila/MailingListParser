"""
This module is used to find the community structure of the network according to the Infomap method of Martin Rosvall
and Carl T. Bergstrom and returns an appropriate VertexClustering object. This module has been implemented using both
the iGraph package and the Infomap tool from MapEquation.org. The VertexClustering object represents the clustering of
the vertex set of a graph and also provides some methods for getting the subgraph corresponding to a cluster and such.

"""
import json
import subprocess
import sys
import igraph
import numpy
import networkx as nx
from lib.analysis.author import ranking
from lib.util.read import *

sys.setrecursionlimit(10000)


def write_matrix(json_data, tree_filename="infomap/output/author_graph.tree"):
    """
    Writes to a CSV file the Author Score, In-Degree, Out-Degree, Clustering Coeff, Module Flow coefficient
    ascertainend from the output of the infomaps algorithm.

    :param json_data: Path of the JSON file containing the dataset under analysis
    :param tree_filename: Path of the tree file generated by Infomap detection module
    :return: None
    """
    top_authors = set()
    top_authors_data = dict()
    author_scores = ranking.get(active_score=2, passive_score=1, write_to_file=False)
    index = 0
    for email_addr, author_score in author_scores:
        index += 1
        top_authors.add(email_addr)
        top_authors_data[email_addr] = [author_score]
        if index == 100:
            break

    print("Adding nodes to author's graph...")
    author_graph = nx.DiGraph()
    for msg_id, message in json_data.items():
        if message['From'] in top_authors:
            if message['Cc'] is None:
                addr_list = message['To']
            else:
                addr_list = message['To'] | message['Cc']
            for to_address in addr_list:
                if to_address in top_authors:
                    if author_graph.has_edge(message['From'], to_address):
                        author_graph[message['From']][to_address]['weight'] *= \
                            author_graph[message['From']][to_address]['weight'] / (author_graph[message['From']][to_address]['weight'] + 1)
                    else:
                        author_graph.add_edge(message['From'], to_address, weight=1)

    author_graph_undirected = author_graph.to_undirected()
    clustering_coeff = nx.clustering(author_graph_undirected)
    in_degree_dict = author_graph.in_degree(nbunch=author_graph.nodes_iter())
    out_degree_dict = author_graph.out_degree(nbunch=author_graph.nodes_iter())

    for email_addr in top_authors:
        top_authors_data[email_addr].append(in_degree_dict[email_addr])
        top_authors_data[email_addr].append(out_degree_dict[email_addr])
        top_authors_data[email_addr].append(clustering_coeff[email_addr])

    print("Parsing", tree_filename + "...")
    with open(tree_filename, 'r') as tree_file:
        for line in tree_file:
            if not line or line[0] == '#':
                continue
            line = line.split()
            if line[2][1:-1] in top_authors:
                top_authors_data[line[2][1:-1]].append(float(line[1]))
        tree_file.close()

    with open("top_authors_data.csv", 'w') as output_file:
        output_file.write("Email Address,Author Score,In-Degree,Out-Degree,Clustering Coeff,Module Flow\n")
        for email_addr, data_list in top_authors_data.items():
            output_file.write(email_addr+","+",".join([str(x) for x in data_list])+"\n")
        output_file.close()
    print("Authors data written to file.")
    

def write_pajek_for_submodules(json_data, tree_filename="infomap/output/author_graph.tree"):
    """
    Writes Pajek file that is compatible with the Infomap community detection script for sub-communities/sub-modules

    :param tree_filename: Path of the tree file generated by Infomap detection module
    :param json_data: Path of the JSON file containing the dataset under analysis
    :return: None
    """
    current_module = 1
    authors_in_module = set()
    with open(tree_filename, 'r') as tree_file:
        for line in tree_file:

            if line[0] == '#':
                continue

            if int(line[:line.index(":")]) > current_module:
                author_graph = nx.DiGraph()
                for msg_id, message in json_data.items():
                    if message['Cc'] is None:
                        addr_list = message['To']
                    else:
                        addr_list = message['To'] | message['Cc']
                    # Adding only the required edges to the authors graph:
                    for to_address in addr_list & authors_in_module:
                        if author_graph.has_edge(message['From'], to_address):
                            author_graph[message['From']][to_address]['weight'] += 1
                        else:
                            author_graph.add_edge(message['From'], to_address, weight=1)
                output_filename = "submodule_"+str(current_module)+".net"
                write_pajek(author_graph, filename=output_filename)
                # Run the infomaps algorithm
                output_folder = 'output_submodule' + str(current_module) + "/"
                subprocess.run(args=['mkdir', output_folder])
                subprocess.run(args=['./infomap/Infomap', output_filename + ' ' + output_folder
                               +' --tree --bftree --btree -d -c --node-ranks --flow-network --map'])

                current_module += 1
                authors_in_module = {line[line.index("\"")+1:line.rindex("\"")]}
            else:
                authors_in_module.add(line[line.index("\"")+1:line.rindex("\"")])
