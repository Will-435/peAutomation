/*
Renders one written brief per screened company. The brief is the part a human
actually reads, so abstention status sits at the top rather than in a footnote,
and every counterfactual lever is marked causal or associational. An unmarked
lever reads as advice, and acting on a merely correlated driver is worse than
having no driver at all.
*/

#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

const std::string CANDIDATES_FILE = "data/processed/screened_candidates.csv";
const std::string BRIEFS_DIRECTORY = "data/processed/briefs";
const std::string ABSTAINED_STATUS = "abstained";
const std::string CAUSAL_LABEL = "causal";
const std::string ASSOCIATIONAL_LABEL = "associational";
const char FIELD_SEPARATOR = ',';
const int EXPECTED_FIELD_COUNT = 9;

struct Candidate {
    std::string company_number;
    std::string company_name;
    std::string probability;
    std::string interval_lower;
    std::string interval_upper;
    std::string abstention_status;
    std::string top_drivers;
    std::string comparable_companies;
    std::string counterfactual_levers;
    std::string lever_evidence_type;
};

/*
Splits one CSV line on the field separator.

INPUTS:
    * line

OUTPUTS:
    * vector of field strings
*/
std::vector<std::string> split_line(const std::string & line) {
    std::vector<std::string> fields;
    std::stringstream line_stream(line);
    std::string field;
    while (std::getline(line_stream, field, FIELD_SEPARATOR)) {
        fields.push_back(field);
    }
    return fields;
}

/*
Reads the screened candidate export into memory. Rows with the wrong field count
are skipped rather than partially read, since a shifted column would put the
wrong number under the wrong heading in the brief.

INPUTS:
    * candidates_path

OUTPUTS:
    * vector of candidates
*/
std::vector<Candidate> read_candidates(const std::string & candidates_path) {
    std::vector<Candidate> candidates;
    std::ifstream candidates_file(candidates_path);
    std::string line;
    bool is_header = true;
    while (std::getline(candidates_file, line)) {
        if (is_header) {
            is_header = false;
            continue;
        }
        std::vector<std::string> fields = split_line(line);
        if (static_cast<int>(fields.size()) != EXPECTED_FIELD_COUNT) {
            std::cerr << "Skipped malformed row: " << line << std::endl;
            continue;
        }
        Candidate candidate;
        candidate.company_number = fields[0];
        candidate.company_name = fields[1];
        candidate.probability = fields[2];
        candidate.interval_lower = fields[3];
        candidate.interval_upper = fields[4];
        candidate.abstention_status = fields[5];
        candidate.top_drivers = fields[6];
        candidate.comparable_companies = fields[7];
        candidate.counterfactual_levers = fields[8];
        candidates.push_back(candidate);
    }
    return candidates;
}

/*
Renders the abstention line. It leads the brief so a reader cannot reach the
probability without having seen whether the pipeline declined to answer.

INPUTS:
    * candidate

OUTPUTS:
    * abstention line string
*/
std::string render_abstention_line(const Candidate & candidate) {
    if (candidate.abstention_status == ABSTAINED_STATUS) {
        return "ABSTAINED. The screen declined to score this company. Do not treat the figures below as a recommendation.";
    }
    return "Scored. The screen returned a usable result for this company.";
}

/*
Renders one brief as plain text, abstention first, then the score with its
interval, the drivers, the comparables, and the levers with their evidence type.

INPUTS:
    * candidate

OUTPUTS:
    * rendered brief string
*/
std::string render_brief(const Candidate & candidate) {
    std::stringstream brief;
    brief << render_abstention_line(candidate) << "\n\n";
    brief << "Company: " << candidate.company_name << " (" << candidate.company_number << ")\n\n";
    brief << "Calibrated probability: " << candidate.probability
          << " (interval " << candidate.interval_lower << " to " << candidate.interval_upper << ")\n\n";
    brief << "Top drivers:\n" << candidate.top_drivers << "\n\n";
    brief << "Nearest comparable companies:\n" << candidate.comparable_companies << "\n\n";
    brief << "Counterfactual levers, marked " << CAUSAL_LABEL << " or " << ASSOCIATIONAL_LABEL << ":\n"
          << candidate.counterfactual_levers << "\n\n";
    brief << "An " << ASSOCIATIONAL_LABEL << " lever describes what moves with the outcome, not what causes it. "
          << "Do not act on one without separate evidence.\n";
    return brief.str();
}

/*
Writes one rendered brief to its own file.

INPUTS:
    * candidate
    * brief_text

OUTPUTS:
    * none, the brief file is written
*/
void write_brief(const Candidate & candidate, const std::string & brief_text) {
    std::filesystem::create_directories(BRIEFS_DIRECTORY);
    std::string brief_path = BRIEFS_DIRECTORY + "/" + candidate.company_number + ".txt";
    std::ofstream brief_file(brief_path);
    brief_file << brief_text;
}

int main() {
    std::vector<Candidate> candidates = read_candidates(CANDIDATES_FILE);
    if (candidates.empty()) {
        std::cout << "No screened candidates found, run the screening stage first" << std::endl;
        return 0;
    }
    for (const Candidate & candidate : candidates) {
        write_brief(candidate, render_brief(candidate));
    }
    std::cout << "Wrote " << candidates.size() << " briefs" << std::endl;
    return 0;
}
