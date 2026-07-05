#!/usr/bin/env python

import argparse
import os
from datetime import datetime

import yaml
from github import Auth, Github

def pause(env, service, repository, new_branch):

    file_path = f'envs/{env}/{service}/image-updater.yaml' 
    contents = repository.get_contents(file_path, ref=repository.default_branch)
    app = yaml.safe_load(contents.decoded_content.decode())
    app['spec']['applicationRefs'][0]["images"][0].update({'commonUpdateSettings': {"ignoreTags": ["*"]}})
    img_upd_yaml = yaml.dump(app, default_flow_style=False, explicit_start=True, sort_keys=False)
    repository.update_file(contents.path, f'Pause {service} in {env}.', img_upd_yaml, contents.sha, branch=new_branch)
    print(f'Updated the "{file_path}" file in the "{new_branch}" branch of the "{repository.name}" remote repository')


def resume(env, service, repo, new_branch):

    file_path = f'envs/{env}/{service}/image-updater.yaml' 
    contents = repo.get_contents(file_path, ref=repo.default_branch)
    app = yaml.safe_load(contents.decoded_content.decode())
    print(app['spec']['applicationRefs'][0]["images"][0])
    app['spec']['applicationRefs'][0]["images"][0].pop('commonUpdateSettings', None)
    app_yaml = yaml.dump(app, default_flow_style=False, explicit_start=True, sort_keys=False)
    repo.update_file(contents.path, f'Resume {service} in {env}.', app_yaml, contents.sha, branch=new_branch)
    print(f'Updated the "{file_path}" file in the "{new_branch}" branch of the "{repo.name}" remote repository')


def get_versions(helm_charts_dir, env, repo):

    versions = {}
    services = repo.get_contents(helm_charts_dir)
    for service in services:
        file_path = f'{service.path}/.argocd-source-{service.name}-{env}.yaml'
        contents = repo.get_contents(file_path, ref=repo.default_branch)
        params = yaml.safe_load(contents.decoded_content.decode())
        for param in params['helm']['parameters']:
            if param['name'] == 'image.tag':
                versions[service.name] = param['value']
    return versions


def options():

    parser = argparse.ArgumentParser()
    parser.add_argument('--source-env', help='Select environment')
    parser.add_argument('--target-env', help='Select environment')
    parser.add_argument('--action', help='Select an action to perform')
    return parser.parse_args()


def update_versions(env, latest_versions, repo, branch):

    target_dir = f'envs/{env}'
    services = repo.get_contents(target_dir)
    for service in services:
        file_path = f'{service.path}/application.yaml'
        contents = repo.get_contents(file_path, ref=repo.default_branch)
        app = yaml.safe_load(contents.decoded_content.decode())
        new_params = []
        for param in app['spec']['source']['helm']['parameters']:
            if param['name'] != 'image.tag':
                new_params.append(param)
            

        image_tag = {'name': 'image.tag', 'value': latest_versions[service.name]}
        new_params.append(image_tag)
        print(new_params)
        app['spec']['source']['helm']['parameters'] = new_params
        app_yaml = yaml.dump(app, default_flow_style=False, explicit_start=True)
        repo.update_file(contents.path, f'Updated {service.name} in {env}.', app_yaml, contents.sha, branch=branch)
        print(f'Updated the "{file_path}" file in the "{branch}" branch of the "{repo.name}" remote repository')


def create_branch(repository, new_branch):
    default_branch = repository.get_branch(repository.default_branch)
    repository.create_git_ref(ref='refs/heads/' + new_branch, sha=default_branch.commit.sha)
    print(f'Created a "{new_branch}" branch in the "{repository.name}" remote repository')


def create_pr(repository, new_branch, title):
    base = repository.default_branch
    repository.create_pull(base=base, head=new_branch, title=title)
    print(f'Created a pull request in the "{repository.name}" remote repository')


def get_repo(name):
    github_token = os.environ['GITHUB_TOKEN']
    auth = Auth.Token(github_token)
    g = Github(auth=auth)
    return g.get_repo(name)


def main():
    repository = get_repo('waqcas/k8s_argo_environments')
    args = options()
    today = datetime.today().strftime('%Y-%m-%d')
    env_dir = f'envs/{args.target_env}'
    if args.action == 'pause':
        new_branch = f'pause-{args.target_env}-{today}'
        create_branch(repository, new_branch)
        services = repository.get_contents(env_dir)
        for svc in services:
            pause(args.target_env, svc.name, repository, new_branch)

        create_pr(repository, new_branch, f'Freeze the {args.target_env} environment.')

    if args.action == 'resume':
        print("resume started")
        new_branch = f'resume-{args.target_env}-{today}'
        print(new_branch)
        create_branch(repository, new_branch)
        services = repository.get_contents(env_dir)
        for svc in services:
            resume(args.target_env, svc.name, repository, new_branch)

        create_pr(repository, new_branch, f'Unfreeze the {args.target_env} environment.')

    if args.action == 'push':
        new_branch = f'prod-push-{today}'
        create_branch(repository, new_branch)
        latest_versions = get_versions('helm-charts', args.source_env, repository)
        print(f'latest versions {latest_versions}')
        update_versions(args.target_env, latest_versions, repository, new_branch)
        create_pr(repository, new_branch, f'Production Push.')


if __name__ == "__main__":
    main()
