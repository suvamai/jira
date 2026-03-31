pipeline {
    agent any

    options {
        timeout(time: 4, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '100'))
        disableConcurrentBuilds()
    }

    triggers {
        cron('H/5 * * * *')
    }

    environment {
        JIRA_BASE_URL     = 'https://rkdgroup.atlassian.net'
        JIRA_EMAIL        = credentials('DSLF_JIRA_EMAIL')
        JIRA_API_TOKEN    = credentials('DSLF_JIRA_API_TOKEN')
        ANTHROPIC_API_KEY = credentials('DSLF_ANTHROPIC_API_KEY')
        MS_CLIENT_ID      = credentials('DSLF_MS_CLIENT_ID')
        MS_TENANT_ID      = credentials('DSLF_MS_TENANT_ID')
        IMAP_EMAIL        = credentials('DSLF_IMAP_EMAIL')
    }

    stages {
        stage('Install deps') {
            steps {
                sh 'pip3 install -q -r requirements.txt'
            }
        }
        stage('Scan emails') {
            steps {
                sh 'python3 email_scanner/email_scanner.py'
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'email_scanner/logs/*.log',
                             allowEmptyArchive: true
        }
        failure {
            echo 'Scan failed — check archived logs above.'
        }
    }
}
