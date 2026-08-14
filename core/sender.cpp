/*
Sends the rendered briefs by email. The content is sent exactly as email_output.cpp
produced it and is never edited here, so what was reviewed is what goes out. A
brief the pipeline declined to score is not sent at all, since an abstention that
reaches an inbox looks like a recommendation.

Requires libcurl. Build with: g++ sender.cpp -lcurl -o sender
*/

#include <curl/curl.h>

#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

const std::string CONFIG_FILE = "config.env";
const std::string BRIEFS_DIRECTORY = "data/processed/briefs";
const std::string DISPATCH_LOG_FILE = "data/processed/dispatch_log.txt";
const std::string ABSTAINED_MARKER = "ABSTAINED";
const std::string SMTP_HOST_KEY = "SMTP_HOST";
const std::string SMTP_USER_KEY = "SMTP_USER";
const std::string SMTP_PASSWORD_KEY = "SMTP_PASSWORD";
const std::string SENDER_ADDRESS_KEY = "SENDER_ADDRESS";
const char CONFIG_SEPARATOR = '=';
const char COMMENT_MARKER = '#';
const int MAXIMUM_ATTEMPTS = 3;

/*
Reads the gitignored key and value config file. Credentials are never written
into this source file, so the same binary can be shared without leaking them.

INPUTS:
    * config_path

OUTPUTS:
    * map of config key to value
*/
std::map<std::string, std::string> read_config(const std::string & config_path) {
    std::map<std::string, std::string> settings;
    std::ifstream config_file(config_path);
    std::string line;
    while (std::getline(config_file, line)) {
        if (line.empty() || line[0] == COMMENT_MARKER) {
            continue;
        }
        std::size_t separator_position = line.find(CONFIG_SEPARATOR);
        if (separator_position == std::string::npos) {
            continue;
        }
        std::string key = line.substr(0, separator_position);
        std::string value = line.substr(separator_position + 1);
        settings[key] = value;
    }
    return settings;
}

/*
Reads one rendered brief from file.

INPUTS:
    * brief_path

OUTPUTS:
    * brief text
*/
std::string read_brief(const std::string & brief_path) {
    std::ifstream brief_file(brief_path);
    std::stringstream brief_buffer;
    brief_buffer << brief_file.rdbuf();
    return brief_buffer.str();
}

/*
Checks whether a brief was abstained on. The marker is written at the top of the
brief by email_output.cpp, so the check reads the rendered text rather than
depending on the screening data being available here.

INPUTS:
    * brief_text

OUTPUTS:
    * true when the pipeline declined to score
*/
bool is_abstained(const std::string & brief_text) {
    return brief_text.rfind(ABSTAINED_MARKER, 0) == 0;
}

/*
Appends one dispatch record to the log, so what was sent and when is recoverable
after the fact.

INPUTS:
    * recipient
    * brief_path
    * outcome

OUTPUTS:
    * none, the dispatch log is appended to
*/
void record_dispatch(const std::string & recipient, const std::string & brief_path, const std::string & outcome) {
    std::ofstream dispatch_log(DISPATCH_LOG_FILE, std::ios::app);
    std::time_t sent_at = std::time(nullptr);
    dispatch_log << sent_at << " " << recipient << " " << brief_path << " " << outcome << "\n";
}

/*
Reads the payload into libcurl one chunk at a time as the transfer runs.

INPUTS:
    * buffer
    * size
    * count
    * payload_stream

OUTPUTS:
    * number of bytes copied into the buffer
*/
static std::size_t payload_reader(char * buffer, std::size_t size, std::size_t count, void * payload_stream) {
    std::stringstream * payload = static_cast<std::stringstream *>(payload_stream);
    payload->read(buffer, size * count);
    return payload->gcount();
}

/*
Sends one brief to one recipient over SMTP, retrying a fixed number of times.
The loop stops after the attempts are used up rather than retrying forever, so a
permanently rejected address cannot stall the run.

INPUTS:
    * settings
    * recipient
    * brief_text

OUTPUTS:
    * true when the send succeeded
*/
bool send_brief(const std::map<std::string, std::string> & settings,
                const std::string & recipient,
                const std::string & brief_text) {
    for (int attempt_number = 0; attempt_number < MAXIMUM_ATTEMPTS; attempt_number = attempt_number + 1) {
        CURL * curl_handle = curl_easy_init();
        if (curl_handle == nullptr) {
            return false;
        }
        std::stringstream payload;
        payload << "To: " << recipient << "\r\n";
        payload << "From: " << settings.at(SENDER_ADDRESS_KEY) << "\r\n";
        payload << "Subject: Screening brief\r\n\r\n";
        payload << brief_text;

        struct curl_slist * recipients = nullptr;
        recipients = curl_slist_append(recipients, recipient.c_str());

        curl_easy_setopt(curl_handle, CURLOPT_URL, settings.at(SMTP_HOST_KEY).c_str());
        curl_easy_setopt(curl_handle, CURLOPT_USERNAME, settings.at(SMTP_USER_KEY).c_str());
        curl_easy_setopt(curl_handle, CURLOPT_PASSWORD, settings.at(SMTP_PASSWORD_KEY).c_str());
        curl_easy_setopt(curl_handle, CURLOPT_MAIL_FROM, settings.at(SENDER_ADDRESS_KEY).c_str());
        curl_easy_setopt(curl_handle, CURLOPT_MAIL_RCPT, recipients);
        curl_easy_setopt(curl_handle, CURLOPT_READFUNCTION, payload_reader);
        curl_easy_setopt(curl_handle, CURLOPT_READDATA, &payload);
        curl_easy_setopt(curl_handle, CURLOPT_UPLOAD, 1L);

        CURLcode send_result = curl_easy_perform(curl_handle);
        curl_slist_free_all(recipients);
        curl_easy_cleanup(curl_handle);

        if (send_result == CURLE_OK) {
            return true;
        }
        std::cerr << "Send attempt failed: " << curl_easy_strerror(send_result) << std::endl;
    }
    return false;
}

int main() {
    std::map<std::string, std::string> settings = read_config(CONFIG_FILE);
    if (settings.find(SMTP_HOST_KEY) == settings.end()) {
        std::cout << "No SMTP settings found in " << CONFIG_FILE << std::endl;
        return 0;
    }
    if (!std::filesystem::exists(BRIEFS_DIRECTORY)) {
        std::cout << "No briefs found, run email_output first" << std::endl;
        return 0;
    }
    // Recipients come from the caller once the routing rules are settled.
    std::vector<std::string> recipients;
    if (recipients.empty()) {
        std::cout << "No recipients configured, nothing sent" << std::endl;
        return 0;
    }
    for (const auto & brief_entry : std::filesystem::directory_iterator(BRIEFS_DIRECTORY)) {
        std::string brief_path = brief_entry.path().string();
        std::string brief_text = read_brief(brief_path);
        if (is_abstained(brief_text)) {
            record_dispatch("none", brief_path, "skipped_abstained");
            continue;
        }
        for (const std::string & recipient : recipients) {
            bool was_sent = send_brief(settings, recipient, brief_text);
            record_dispatch(recipient, brief_path, was_sent ? "sent" : "failed");
        }
    }
    return 0;
}
