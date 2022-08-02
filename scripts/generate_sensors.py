"""This script generates the sensor portion of the site, including coverage,
for each YAML sensor mapping file.
"""

import json
import glob
import yaml
from os import path, makedirs
from jinja2 import Template
from operator import itemgetter

# Generate a data model coverage table for a specific data model
def generateDataModelCoverage(name, coverage):
  current_model = None
  for data_model in data_models:
    if data_model["name"] == name:
      current_model = data_model
  actions = [x["name"] for x in current_model["actions"]]
  fields = [x["name"] for x in current_model["fields"]]
  # Build the MD Table
  header_str = "### [{0}](../data_model/{0})\n\n".format(name.lower())
  # Build the MD table header
  md_header = "| |"
  for field in sorted(fields):
    md_header += " `{0}` |".format(field)
  md_header += "\n|"
  md_header += ("---|" * len(fields))
  md_header += "\n"
  # Build the table rows w/ coverage
  rows = ""
  for action in sorted(actions):
    row = "| `{0}` | ".format(action)
    row_vals = [" |"] * len(fields)
    if action_cov := [x for x in coverage if action in x]:
      for item in action_cov:
        field_name = item.split("/")[2]
        row_vals[sorted(fields).index(field_name)] = "✓|"
    for row_val in row_vals:
      row += row_val
    row += "\n"
    rows += row
  return header_str + md_header + rows

def generateSensorsForAnalytics(analytics, sensor_dict):
  row = "- [{}](/sensors/{})"
  # Build the table rows w/ coverage
  for a in analytics:
    print(f"generating sensors for {a}")
    try:
      sensors = list(sensor_dict[a])
    except:
        print("didn't find any associated sensors")
        sensors = []
    rows = [row.format(s, s) for s in sensors]
    if not rows:
      rows.append("Not computed")
    row_str = "\n" + "\n".join(rows) + "\n"

    # insert the coverage into the existing analytic md doc
    new_a = []
    original_a = open(path.join(path.dirname(__file__),"..","docs", "analytics", a,"index.md"), "r").readlines()
    for i,l in enumerate(original_a):
        if "### Implementations" in l:
            ending_tag = i-2 # where to end replacement
        if "### Applicable Sensors" in l:
            beginning_tag = i+1  # where to begin replacement
    try:
      pass
    except:
        continue    # this analytic does not have implementains so no sensor mapping is appropriate
    already_replaced = False
    for i,l in enumerate(original_a):
        if i > ending_tag or i < beginning_tag:
          new_a.append(l)
        elif already_replaced == False:
          # this is the spot where we place the new content
          new_a.append(row_str)
          already_replaced = True
    with open(f"../docs/analytics/{a}/index.md", "w") as af:
      af.write("".join(new_a))

# Get all analytics and load as list of dicts
analytics_files = glob.glob(path.join(path.dirname(__file__), "..", "analytics", "*.yaml"))
analytics = [yaml.load(open(analytic_file).read()) for analytic_file in analytics_files]

# Get all sensor mappings and load as a list of dicts
mapping_files = glob.glob(path.join(path.dirname(__file__), "..", "sensors", "*.yaml"))
print(f"detected the following sensors: {str(mapping_files)}")
mappings = [yaml.load(open(mapping_file,encoding='utf-8').read()) for mapping_file in mapping_files]

# Get all data models and load as list of dicts
data_model_files = glob.glob(path.join(path.dirname(__file__), "..", "data_model", "*.yaml"))
data_models = []
for dmf in data_model_files:
  print(f"working on {dmf}")
  data_models.append(yaml.load(open(dmf).read()))
#data_models = [yaml.load(open(data_model_file).read()) for data_model_file in data_model_files]

# Parse each analytic to find its data model references (if any)
analytics_refs = {}
for analytic in analytics:
  if 'data_model_references' in analytic:
    analytic_tag = analytic['id'] + ": " + analytic['title']
    analytics_refs[analytic_tag] = analytic['data_model_references']

# Parse each mapping and build up the "simplified" string representation
# e.g., process/create/parent_exe
sensor_mappings = {}
for sensor in mappings:
  sensor_tag = sensor['sensor_name'] + " " + str(sensor['sensor_version'])
  simplified_mappings = []
  for mapping in sensor['mappings']:
    mapping_str = mapping['object'] + "/" + mapping["action"] + "/{0}"
    simplified_mappings.extend(
        mapping_str.format(field) for field in mapping['fields'])
  sensor['simplified_mappings'] = simplified_mappings

# First, build up the "simplified" string representation
# of each data model so we can compute the intersection
# between sensor coverage
for data_model in data_models:
  simplified_mappings = []
  name = data_model["name"]
  mapping_str = f"{name.lower()}/" + "{0}" + "/" + "{1}"
  actions = [x["name"] for x in data_model["actions"]]
  fields = [x["name"] for x in data_model["fields"]]
  for action in actions:
    for field in fields:
      simplified_str = mapping_str.format(action, field)
      simplified_mappings.append(simplified_str)
  data_model["simplified_mappings"] = simplified_mappings

# Compare the analytic data model refs to the sensor mappings
# to find the analytic coverage of each sensor
# similarly, compute the data model coverage
sensors_analytics_dict = {}
for sensor in mappings:
  if 'simplified_mappings' in sensor:
    analytic_coverage = []
    data_model_coverage = []
    # Compute the analytic coverage
    for analytic, refs in analytics_refs.items():
      if intersection := list(set(sensor['simplified_mappings']) & set(refs)):
        #for sensor -> analytic mapping:
        i = analytic.split(":")[0]
        analytic_dict = {'id': i,
                         'full_title': analytic}
        analytic_coverage.append(analytic_dict)
        # for analytic -> sensor mapping:
        sensors_analytics_dict.setdefault(
            i,
            []).append(f"{sensor['sensor_name']}_{sensor['sensor_version']}")

    if analytic_coverage:
      if 'other_coverage' in sensor:
          for coverage in sensor['other_coverage']:
               analytic_dict = {'id': coverage.split(':')[0],
                                'full_title': coverage}
               analytic_coverage.append(analytic_dict)
      newlist = sorted(analytic_coverage, key=itemgetter('id'))
      sensor['analytic_coverage'] = newlist
      # Compute the data model coverage
      for data_model in data_models:
        name = data_model["name"]
        if intersection := list(
            set(sensor['simplified_mappings'])
            & set(data_model['simplified_mappings'])):
          if "data_model_coverage" not in sensor:
              sensor["data_model_coverage"] = []
          sensor["data_model_coverage"].append(generateDataModelCoverage(name,intersection))

# fill in the sensor info on each analytic page
generateSensorsForAnalytics([path.split(a)[-1].strip(".yaml") for a in analytics_files], sensors_analytics_dict)

# Get the template file for the sensor page. Note that this is a markdown template which will be rendered by GH Pages.
sensor_template = Template(open('sensor_template.md').read())

# Generate the sensor page for each sensor
for sensor in mappings:
  sensor_tag = sensor['sensor_name'] + "_" + str(sensor['sensor_version'])
  # Generate the markdown
  markdown = sensor_template.render(sensor=sensor)
  # Save to the sensors directory
  open(f'../docs/sensors/{sensor_tag.lower()}.md', 'w').write(markdown)
