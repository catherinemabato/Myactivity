import json
from collections import Counter


with open("new_model_failures_with_bad_commit.json") as fp:
    data = json.load(fp)


team_members = ["ydshieh", "zucchini-nlp"]

# Counting the number of failures grouped by authors
new_data = {}
for model, model_result in data.items():
    for device, failed_tests in model_result.items():
        for failed_test in failed_tests:
            author = failed_test["author"]

            if not author in team_members:
                author = failed_test["merged_by"]

            if author not in new_data:
                new_data[author] = Counter()
            new_data[author].update([model])
for author in new_data:
    new_data[author] = dict(new_data[author])

# # Group by author
# new_data_full = {author: deepcopy(data) for author in new_data}
# for author, _data in new_data_full.items():
#     for model, model_result in _data.items():
#         for device, failed_tests in model_result.items():
#             failed_tests = [x for x in failed_tests if x["author"] == author or x["merged_by"] == author]
#             model_result[device] = failed_tests
# print(json.dumps(new_data_full, indent=4))

# Add `GH_` prefix as keyword mention
output = {}
for author, item in new_data.items():
    author = f"GH_{author}"
    output[author] = item

print(json.dumps(output, indent=4).replace('"', '\\"').replace("\n", "\\n"))
