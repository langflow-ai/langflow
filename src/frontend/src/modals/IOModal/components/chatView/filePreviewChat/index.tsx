export default function FilePreview(
    { error, file, loading }:
        { loading: boolean, file: File, error: boolean }
) {
    return (
        <div>
            {loading && <div>Loading...</div>}
            {error && <div>Error...</div>}
            <div>{file.name}</div>
        </div>
    )

}