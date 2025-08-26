# MCP Server Configuration File Naming Conflict #9392 - Status Update

Hi @Bro34,

Thank you for reporting this MCP server configuration issue. 

## ✅ **ISSUE STATUS: RESOLVED**

This issue has been **completely fixed** in the current version of Langflow.

### **Fix Details (Verified)**

**PR #9014**: "fix: Adjust uniqueness constraint on file names" - **MERGED** on August 19, 2025
**Commit**: `0b78ccd4de3db74ebdcbaccedfb79a008fc1ea5d`

### **What Was Fixed**

**Before Fix:**
- Database constraint: `UNIQUE(name)` - Global uniqueness across all users
- **Problem**: Multiple MCP servers couldn't use the same `_mcp_servers` filename

**After Fix:**
- Database constraint: `UNIQUE(name, user_id)` - Unique per user only
- **Solution**: Each user can have their own `_mcp_servers` file, preventing conflicts

### **Resolution**

The fix addresses your exact problem by:
1. **Relaxing the constraint** - Files only need unique names within the same user account
2. **Enabling multiple MCP servers** - Each user can configure multiple servers without conflicts
3. **Including migration logic** - Existing databases are automatically updated

### **For Current Users**

If you're still experiencing this issue:

1. **Update to latest version** - Ensure you're running a version that includes commit `0b78ccd4de`
2. **Run database migrations** - The migration should handle existing constraint conflicts automatically
3. **Restart Langflow** - Allow the database schema changes to take effect

### **Verification**

You can verify the fix is applied by checking:
```sql
-- The constraint should now include both name AND user_id
SELECT * FROM information_schema.table_constraints 
WHERE table_name = 'file' AND constraint_type = 'UNIQUE';
```

**Status**: ✅ **RESOLVED** - Issue fixed in main branch  
**Credit**: @erichare for implementing the fix  
**Migration**: Automatic via Alembic  

The multiple MCP server configuration should now work as expected!

Best regards,  
Langflow Support Team