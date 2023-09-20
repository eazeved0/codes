import boto3
import sys
from collections import defaultdict
from tabulate import tabulate

def list_attached_resources_for_security_groups(region_name):
    try:
        # Remove leading and trailing whitespaces from the region name
        region_name = region_name.strip()
        
        ec2 = boto3.client('ec2', region_name=region_name)
        elb = boto3.client('elb', region_name=region_name)
        elbv2 = boto3.client('elbv2', region_name=region_name)
        lambda_client = boto3.client('lambda', region_name=region_name)
        rds = boto3.client('rds', region_name=region_name)
        elasticache = boto3.client('elasticache', region_name=region_name)
        eks = boto3.client('eks', region_name=region_name)  # Add EKS client
        efs = boto3.client('efs', region_name=region_name)  # Add EFS client
        
        # Retrieve all existing EFS file systems and their IDs
        efs_response = efs.describe_file_systems()
        efs_file_systems = {fs['FileSystemId']: fs for fs in efs_response.get('FileSystems', [])}
        
        response = ec2.describe_security_groups()
        attached_resources = defaultdict(list)
        processed_eks_clusters = set()
        
        for security_group in response['SecurityGroups']:
            sg_id = security_group['GroupId']
            ec2_response = ec2.describe_instances(Filters=[{'Name': 'instance.group-id','Values': [sg_id]}])
            for r in ec2_response.get('Reservations', []):
                for i in r.get('Instances', []):
                    attached_resources[i['InstanceId']].append(('EC2 Instance', i['InstanceId']))
            
            clb_response = elb.describe_load_balancers()
            for clb in clb_response.get('LoadBalancerDescriptions', []):
                if sg_id in clb.get('SecurityGroups', []):
                    attached_resources[clb['LoadBalancerName']].append(('Classic Load Balancer', clb['LoadBalancerName']))
           
            elbv2_response = elbv2.describe_load_balancers(Names=[])
            for alb in elbv2_response.get('LoadBalancers', []):
                for alb_sg in alb.get('SecurityGroups', []):
                    if alb_sg == sg_id:
                        attached_resources[alb['LoadBalancerArn'].split('/')[-1]].append(('Load Balancer', alb['LoadBalancerArn'].split('/')[-1]))
           
            lambda_response = lambda_client.list_functions(FunctionVersion='ALL')
            for function in lambda_response.get('Functions', []):
                fn_id = function['FunctionName']
                if sg_id in function.get('VpcConfig', {}).get('SecurityGroupIds', []):
                    attached_resources[fn_id].append(('Lambda Function', fn_id))
           
            rds_response = rds.describe_db_instances()
            for db_instance in rds_response.get('DBInstances', []):
                for db_sg in db_instance.get('VpcSecurityGroups', []):
                    if db_sg['VpcSecurityGroupId'] == sg_id:
                        attached_resources[db_instance['DBInstanceIdentifier']].append(('RDS Instance', db_instance['DBInstanceIdentifier']))
           
            elasticache_response = elasticache.describe_cache_clusters()
            for cache_cluster in elasticache_response.get('CacheClusters', []):
                for sg in cache_cluster.get('SecurityGroups', []):
                    if sg['SecurityGroupId'] == sg_id:
                        attached_resources[cache_cluster['CacheClusterId']].append(('ElasticCache Cluster', cache_cluster['CacheClusterId']))
        
            # EKS cluster resources
            eks_response = eks.list_clusters()
            for cluster_name in eks_response.get('clusters', []):
                if cluster_name not in processed_eks_clusters:
                    cluster_info = eks.describe_cluster(name=cluster_name)
                    attached_resources[cluster_name].append(('EKS Cluster', cluster_name))
                    processed_eks_clusters.add(cluster_name)
            
            # EFS Mount Targets
            efs_mount_targets_response = efs.describe_mount_targets()
            for mount_target in efs_mount_targets_response.get('MountTargets', []):
                for sg in mount_target.get('SecurityGroups', []):
                    if sg == sg_id:
                        file_system_id = mount_target['FileSystemId']
                        attached_resources[mount_target['MountTargetId']].append(('EFS Mount Target', file_system_id))
       
        table = []
        for resource_name, resource_list in attached_resources.items():
            for resource_type, resource_id in resource_list:
                table.append([resource_name, resource_type, resource_id])
       
        headers = ["Resource Name", "Resource Type", "Resource ID"]
        print(tabulate(table, headers, tablefmt="grid"))
    
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python list_attached_resources.py <region_name>")
    else:
        region_name = sys.argv[1]
        list_attached_resources_for_security_groups(region_name)

