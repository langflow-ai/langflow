def job_factory(flow_id):
    def job_function():
        # This function can now access flow_id and perform operations based on it
        print(f"Executing job for flow_id: {flow_id}")
        # Suppose we call some other function that does the actual work
        # perform_task(flow_id)

    return job_function
