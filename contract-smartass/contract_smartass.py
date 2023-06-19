import base64
import ei_pb2
import itertools
import json
import random
import requests
import timeit
import utils
from google.protobuf import json_format
from itertools import combinations

user_id = "EIXXXXXX"
fetch = False
download = False
print_db = False

optimize_coop = True  # True = optimize coop / False = optimize single player

# for single-player optimization only
username = "XXXXXX"
deflector_effect = 1
has_pro_permit = True
use_deflector = True
num_iterations_single = 1  # higher = more accurate time estimate, but slower

# for coop optimization only
coop_size = 10
num_iterations_coop = 1  # higher = more accurate time estimate, but slower
consistent_results = False # True = consistent players / False = randomized players

BASE_SHIPPING = 119134368896484.375 * 60
BASE_LAYING = 5544 * 60 * 11340000000

ARTIFACT_NAMES = {
    0: "Totem",
    3: "Medallion",
    4: "Beak",
    5: "LoE",
    6: "Necklace",
    7: "Vial",
    8: "Gusset",
    9: "Chalice",
    10: "BoB",
    11: "Feather",
    12: "Ankh",
    21: "Brooch",
    22: "Rainstick",
    23: "Cube",
    24: "Metronome",
    25: "SiaB",
    26: "Deflector",
    27: "Compass",
    28: "Monocle",
    29: "Actuator",
    30: "Lens",
    1: "Tachyon Stone",
    31: "Dilithium Stone",
    32: "Shell Stone",
    33: "Lunar Stone",
    34: "Soul Stone",
    39: "Prophecy Stone",
    36: "Quantum Stone",
    37: "Terra Stone",
    38: "Life Stone",
    40: "Clarity Stone",
    17: "Gold Meteorite",
    18: "Tau Ceti Geode",
    43: "Solar Titanium",
    2: "Tachyon Stone Fragment",
    44: "Dilithium Stone Fragment",
    45: "Shell Stone Fragment",
    46: "Lunar Stone Fragment",
    47: "Soul Stone Fragment",
    48: "Prophecy Stone Fragment",
    49: "Quantum Stone Fragment",
    50: "Terra Stone Fragment",
    51: "Life Stone Fragment",
    52: "Clarity Stone Fragment",
}

ARTIFACT_RARITIES = {
    0: "C",
    1: "R",
    2: "E",
    3: "L",
}

GUSSET_EFFECTS = {
    "T1C": 1.05,
    "T2C": 1.1,
    "T2E": 1.12,
    "T3C": 1.15,
    "T3R": 1.16,
    "T4C": 1.2,
    "T4E": 1.22,
    "T4L": 1.25,
}

METRONOME_EFFECTS = {
    "T1C": 1.05,
    "T2C": 1.1,
    "T2R": 1.12,
    "T3C": 1.15,
    "T3R": 1.17,
    "T3E": 1.2,
    "T4C": 1.25,
    "T4R": 1.27,
    "T4E": 1.3,
    "T4L": 1.35,
}

COMPASS_EFFECTS = {
    "T1C": 1.05,
    "T2C": 1.1,
    "T3C": 1.2,
    "T3R": 1.22,
    "T4C": 1.3,
    "T4R": 1.35,
    "T4E": 1.4,
    "T4L": 1.5,
}

DEFLECTOR_EFFECTS = {
    "T1C": 1.05,
    "T2C": 1.08,
    "T3C": 1.12,
    "T3R": 1.13,
    "T4C": 1.15,
    "T4R": 1.17,
    "T4E": 1.19,
    "T4L": 1.20,
}

CONTRACT_ARTIFACTS = ["Gusset", "Metronome", "Deflector", "Compass"]


class FirstContactData():
    def __init__(self, user_id, username="", fetch=True):
        self.user_id = user_id
        self.data = ei_pb2.EggIncFirstContactResponse()

        if fetch:
            self.__fetch_FirstContactResponse()
            self.username = self.data.backup.user_name

            # slice FirstContactResponse string to select inventory data
            json_string = json_format.MessageToJson(self.data)
            json_string = json_string[0:json_string.index("backup")+15] \
                + json_string[json_string.index("artifactsDb")-1:json_string.index("\"gameServicesId")-6] \
                + json_string[-6:]

            json_string = json_string[0:json_string.index("\"itemSequence")-8] \
                + json_string[-12:]

            # overwrite original data with new sliced data
            self.data = ei_pb2.EggIncFirstContactResponse()
            json_format.Parse(json_string, self.data)
        else:
            self.username = username
            self.__load_FirstContactResponse()

        self.artifacts_db = self.data.backup.artifacts_db.inventory_items

        self.potential_candidates = {}
        self.best_rate = 0
        self.best_combo = []
        self.num_combos_checked = []

        # discard stones, fragments, and LoE
        self.__preprocess_artifacts_db(True)

    def __fetch_FirstContactResponse(self):
        first_contact_request = ei_pb2.EggIncFirstContactRequest()
        first_contact_request.ei_user_id = self.user_id
        first_contact_request.client_version: 50

        url = "https://ctx-dot-auxbrainhome.appspot.com/ei/bot_first_contact"
        data = {"data": base64.b64encode(
            first_contact_request.SerializeToString()).decode("utf-8")}
        response = requests.post(url, data=data)

        self.data.ParseFromString(base64.b64decode(response.text))

    def __load_FirstContactResponse(self):
        json_file = json.load(
            open(f"../artifact-data/FirstContactResponse_{self.username}.json", "r"))
        json_format.Parse(json.dumps(json_file), self.data)

    def __preprocess_artifacts_db(self, remove_loe):
        VALID_ARTIFACT_NAMES = ["Totem", "Medallion", "Beak", "Necklace",
                                "Vial", "Gusset", "Chalice", "BoB", "Feather",
                                "Ankh", "Brooch", "Rainstick", "Cube",
                                "Metronome", "SiaB", "Deflector", "Compass",
                                "Monocle", "Actuator", "Lens"]

        new_artifacts_db = []

        for item in self.artifacts_db:
            name = ARTIFACT_NAMES[item.artifact.spec.name]

            if name in VALID_ARTIFACT_NAMES or (not remove_loe and name == "LoE"):
                new_artifacts_db.append(item)

        self.artifacts_db = new_artifacts_db

    def __create_tier(self, spec):
        return "T" + str(spec.level + 1) + ARTIFACT_RARITIES[spec.rarity]

    def download_FirstContactResponse(self):
        with open(f"../artifact-data/FirstContactResponse_{self.username}.json", "w") as json_file:
            json_file.write(json_format.MessageToJson(self.data))

    def find_candidates(self):
        CONTRACT_STONES = ["Quantum Stone", "Tachyon Stone"]

        self.potential_candidates = {}

        # find artifacts from CONTRACT_ARTIFACTS or with CONTRACT_STONES
        for item in self.artifacts_db:
            name = ARTIFACT_NAMES[item.artifact.spec.name]
            tier = self.__create_tier(item.artifact.spec)
            stones = item.artifact.stones

            is_candidate = False

            if name in CONTRACT_ARTIFACTS:
                is_candidate = True
            elif tier[-1] != "C":
                for stone in stones:
                    if ARTIFACT_NAMES[stone.name] in CONTRACT_STONES:
                        is_candidate = True
                        break

            if is_candidate:
                candidate = Artifact(name, tier, stones)

                # TODO: Deal with duplicated code below 1

                if not self.potential_candidates.get(name):
                    self.potential_candidates[name] = [candidate]
                else:
                    add_candidate = True
                    worst_artifacts = set()

                    # keep only the best artifacts from each candidate group
                    for art in self.potential_candidates[name]:
                        if art.shipping_effect >= candidate.shipping_effect \
                                and art.laying_effect >= candidate.laying_effect:
                            add_candidate = False
                        elif art.shipping_effect <= candidate.shipping_effect \
                                and art.laying_effect <= candidate.laying_effect:
                            worst_artifacts.add(art)

                    if add_candidate:
                        for art in worst_artifacts:
                            self.potential_candidates[name].remove(art)

                        self.potential_candidates[name].append(candidate)

        self.deflector_candidates = self.potential_candidates.pop(
            "Deflector", [])

    def test_combos(self, candidates, slots_to_fill, use_deflector, deflector_effect):
        temp_combos = tuple(combinations(candidates, slots_to_fill))
        combos = []
        num_combos = 0

        # generate every valid group of 4 artifacts
        for i in range(len(temp_combos)):
            for combo in itertools.product(*temp_combos[i]):
                if use_deflector:
                    for deflector in self.deflector_candidates:
                        combos.append(tuple(list(combo) + [deflector]))
                        num_combos += 1
                else:
                    combos.append(combo)
                    num_combos += 1

        # iterate through all combos and find the best
        best_rate = 0

        for c in combos:
            total_shipping = BASE_SHIPPING
            total_laying = BASE_LAYING * deflector_effect

            for art in c:
                total_shipping *= art.shipping_effect
                total_laying *= art.laying_effect

            if min(total_shipping, total_laying) > best_rate:
                best_rate = min(total_shipping, total_laying)
                best_combo = c

        return best_rate, best_combo, num_combos

    def find_helper(self, has_pro_permit, use_deflector, deflector_effect, excluded):
        potential_candidates = self.potential_candidates.copy()

        slots_to_fill = 2 if has_pro_permit else 0

        if use_deflector:
            slots_to_fill += 1
        else:
            slots_to_fill += 2
            potential_candidates["Deflector"] = self.deflector_candidates

        candidate_groups = {}

        # TODO: Deal with duplicated code below 2

        for name in potential_candidates.keys():
            if name in excluded:
                candidate_groups[name] = potential_candidates[name]
            else:
                for candidate in potential_candidates[name]:
                    if not candidate_groups.get("other"):
                        candidate_groups["other"] = [candidate]
                    else:
                        add_candidate = True
                        worst_artifacts = set()

                        # keep only the best artifacts from each candidate group
                        for art in candidate_groups["other"]:
                            if art.shipping_effect >= candidate.shipping_effect \
                                    and art.laying_effect >= candidate.laying_effect:
                                add_candidate = False
                            elif art.shipping_effect <= candidate.shipping_effect \
                                    and art.laying_effect <= candidate.laying_effect:
                                worst_artifacts.add(art)

                        if add_candidate:
                            for art in worst_artifacts:
                                candidate_groups["other"].remove(art)

                            candidate_groups["other"].append(candidate)

        candidates = []

        for name in candidate_groups.keys():
            candidates.append(candidate_groups[name])

        return tuple(list(self.test_combos(candidates, slots_to_fill, use_deflector, deflector_effect)) + [excluded])

    def find_best_artifacts(self, has_pro_permit, use_deflector, deflector_effect):
        self.best_rate = 0
        self.best_combo = []
        self.num_combos_checked = []

        excluded = CONTRACT_ARTIFACTS.copy()

        if not use_deflector:
            excluded.remove("Deflector")

        redo = True

        # TODO: Only keep track of the artifact that was chosen from the
        # excluded category, rather than all artifacts with the same name

        while redo:
            self.best_rate, self.best_combo, num_combos_checked, excluded = self.find_helper(
                has_pro_permit, use_deflector, deflector_effect, excluded)
            self.num_combos_checked.append(num_combos_checked)

            redo = False

            for c in self.best_combo:
                if c.name not in excluded:
                    redo = True
                    excluded.append(c.name)
                    break


class Artifact():
    def __init__(self, name, tier, stones):
        self.name = name
        self.tier = tier

        self.shipping_effect = 1
        self.laying_effect = 1
        self.deflector_effect = 1

        if name == "Gusset":
            self.laying_effect *= GUSSET_EFFECTS[tier]
        elif name == "Metronome":
            self.laying_effect *= METRONOME_EFFECTS[tier]
        elif name == "Compass":
            self.shipping_effect *= COMPASS_EFFECTS[tier]
        elif name == "Deflector":
            self.deflector_effect *= DEFLECTOR_EFFECTS[tier]

        self.stones = []

        for i in range(len(stones)):
            self.stones.append(
                Stone(ARTIFACT_NAMES[stones[i].name], self.__create_tier(stones[i])))

            self.shipping_effect *= self.stones[i].shipping_effect
            self.laying_effect *= self.stones[i].laying_effect

    def __str__(self):
        base_string = f"{self.tier} {self.name} "
        stones_string = ""

        for stone in self.stones:
            stones_string += f"{stone.tier} {stone.name}"

            if stone != self.stones[-1]:
                stones_string += ", "

        stats_string = f"\n\tShipping: {round(self.shipping_effect, 4)} / Laying: {round(self.laying_effect, 4)}"

        final_string = base_string
        final_string += "\n\t" + stones_string if stones_string != "" else ""
        final_string += stats_string

        return final_string

    def __create_tier(self, stone):
        return "T" + str(stone.level + 2)


class Stone():
    def __init__(self, name, tier):
        STONE_EFFECTS = {
            "T2": 1.02,
            "T3": 1.04,
            "T4": 1.05,
        }

        self.name = name
        self.tier = tier

        self.shipping_effect = STONE_EFFECTS[tier] if name == "Quantum Stone" else 1
        self.laying_effect = STONE_EFFECTS[tier] if name == "Tachyon Stone" else 1


def print_num_candidate_combos(fcd):
    combos_checked_string = f"Candidate combos checked: {utils.format_number(sum(fcd.num_combos_checked))}"

    if len(fcd.num_combos_checked) > 1:
        combos_checked_string += " ("

        for i in range(len(fcd.num_combos_checked)):
            n = fcd.num_combos_checked[i]
            combos_checked_string += utils.format_number(n)

            if i < (len(fcd.num_combos_checked) - 1):
                combos_checked_string += " + "

        combos_checked_string += ")"

    print(combos_checked_string)


def optimize_coop_artifacts():
    valid_usernames = ["inici0", "Maj_Oxion"]

    fcds = []

    for i in range(coop_size):
        if consistent_results:
            user = valid_usernames[i % len(valid_usernames)]
        else:
            user = random.choice(valid_usernames)

        fcd = FirstContactData(user_id=user_id, username=user, fetch=fetch)
        fcd.find_candidates()
        fcds.append(fcd)

    total_combos_checked = 0
    best_total = 0
    best_artifacts = []

    binary_strings = sorted(list(itertools.product(
        [1, 0], repeat=len(fcds))), key=lambda x: x.count(0))
    pointless_iterations = 0

    for options in binary_strings:
        pointless_iterations += 1

        for i in range(len(fcds)):
            for j in range(len(fcds[i].deflector_candidates)):
                total_deflector_effect = 1

                for k in range(len(fcds)):
                    if options[k]:
                        total_deflector_effect = round(
                            total_deflector_effect
                            + (fcds[i].deflector_candidates[j].deflector_effect - 1),
                            2)

                current_total = 0

                for k in range(len(fcds)):
                    fcds[k].find_best_artifacts(has_pro_permit=has_pro_permit,
                                                use_deflector=True if options[k] else False,
                                                deflector_effect=(total_deflector_effect - (fcds[i].deflector_candidates[j].deflector_effect - 1)))
                    total_combos_checked += sum(fcds[k].num_combos_checked)
                    current_total += fcds[k].best_rate

                if current_total > best_total:
                    pointless_iterations = 0

                    best_total = current_total
                    best_artifacts = []

                    for fcd in fcds:
                        best_artifacts.append((fcd.username, fcd.best_combo))
                
                if not options[i]:
                    break

        # TODO: Determine proper threshold based on size of binary_strings
        if pointless_iterations > 100:
            break

    for info in best_artifacts:
        print(info[0], "\n----------------")

        for art in info[1]:
            print(art)
        print("\n")

    print(f"Total rate: {utils.format_number(best_total)} /hr")
    print(f"Candidate combos checked: {utils.format_number(total_combos_checked)}")


if __name__ == "__main__":
    if not optimize_coop:
        fcd = FirstContactData(user_id=user_id, username=username, fetch=fetch)

        if download:
            fcd.download_FirstContactResponse()

        if print_db:
            print(fcd.artifacts_db)

        fcd.find_candidates()
        time_taken = round(timeit.timeit(lambda: fcd.find_best_artifacts(has_pro_permit=has_pro_permit, 
                                                                         use_deflector=use_deflector, 
                                                                         deflector_effect=deflector_effect),
                                         number=num_iterations_single), 4)

        for artifact in fcd.best_combo:
            print(artifact)

        print(f"\nTotal rate: {utils.format_number(fcd.best_rate)} /hr")
        print_num_candidate_combos(fcd)
        print(f"Time taken: {time_taken} s")
    else:
        # TODO: Compare against brute force solution that doesn't stop early

        print("Time taken: ", round(timeit.timeit(lambda: optimize_coop_artifacts(),
                                                  number=num_iterations_coop), 4), "s")
